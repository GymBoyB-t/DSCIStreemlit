import json
import os
import threading

import numpy as np
import pandas as pd
import streamlit as st

DATA_FILE = "totals.json"

# Guards read-modify-write access to DATA_FILE so two people submitting at
# the same time can't clobber each other's counts (lost-update race).
_data_lock = threading.Lock()

# Edit this list to change the questions.
# type: "yesno" | "choice" | "scale" | "number"
# - yesno:  Yes/No question
# - choice: pick one of `options`
# - scale:  slider from `min` to `max`
# - number: pick a whole number from `min` to `max`
QUESTIONS = [
    {
        "key": "chicken_road",
        "text": "Why did the chicken cross the road? :D",
        "type": "yesno",
    },
    {
        "key": "troy_rating",
        "text": "How cool is Troy? (1 = not cool, 100 = maximally cool)",
        "type": "scale",
        "min": 1,
        "max": 100,
        "show_distribution": True,
    },
    {
        "key": "pineapple_pizza",
        "text": "Should pineapple be on pizza?",
        "type": "yesno",
    },
    {
        "key": "frogs_toads",
        "text": "Are frogs or toads better?",
        "type": "choice",
        "options": ["Frogs", "Toads"],
    },
    {
        "key": "government_corrupt",
        "text": "Is our government corrupt?",
        "type": "yesno",
    },
    {
        "key": "number_least",
        "text": "Choose a number 1-10. If you pick the LEAST picked number, you win!",
        "type": "number",
        "min": 1,
        "max": 10,
        "win_rule": "least",
    },
    {
        "key": "number_most",
        "text": "Choose a number 1-10. If you pick the MOST picked number, you win!",
        "type": "number",
        "min": 1,
        "max": 10,
        "win_rule": "most",
    },
]


def default_counts(q):
    if q["type"] == "yesno":
        return {"yes": 0, "no": 0}
    if q["type"] == "choice":
        return {opt: 0 for opt in q["options"]}
    return {str(i): 0 for i in range(q["min"], q["max"] + 1)}  # scale or number


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
    else:
        data = {}

    # Fill in any missing questions so the file stays easy to hand-edit.
    for q in QUESTIONS:
        data.setdefault(q["key"], default_counts(q))
    data.setdefault("total_votes", 0)
    return data


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def render_question(q):
    if q["type"] == "yesno":
        return st.radio(q["text"], ["Yes", "No"], horizontal=True, key=q["key"])
    if q["type"] == "choice":
        return st.radio(q["text"], q["options"], horizontal=True, key=q["key"])
    if q["type"] == "scale":
        return st.slider(q["text"], q["min"], q["max"], (q["min"] + q["max"]) // 2, key=q["key"])
    if q["type"] == "number":
        return st.selectbox(q["text"], list(range(q["min"], q["max"] + 1)), key=q["key"])


def counts_key_for(q, answer):
    if q["type"] == "yesno":
        return "yes" if answer == "Yes" else "no"
    if q["type"] == "choice":
        return answer
    return str(answer)  # scale or number


def smooth(values, sigma=4.0):
    radius = max(1, int(sigma * 3))
    x = np.arange(-radius, radius + 1)
    kernel = np.exp(-(x ** 2) / (2 * sigma ** 2))
    kernel /= kernel.sum()
    padded = np.pad(np.asarray(values, dtype=float), radius, mode="edge")
    return np.convolve(padded, kernel, mode="valid")


def record_vote(answers):
    """Compute win results and persist one submission. Thread-safe."""
    with _data_lock:
        # Re-read fresh so we never overwrite votes saved by someone
        # else while this session was busy answering questions.
        data = load_data()

        wins = {}
        for q in QUESTIONS:
            if q["type"] == "number":
                counts = data[q["key"]]
                vals = list(counts.values())
                target = min(vals) if q["win_rule"] == "least" else max(vals)
                winners = {k for k, v in counts.items() if v == target}
                wins[q["key"]] = str(answers[q["key"]]) in winners

        for q in QUESTIONS:
            key = counts_key_for(q, answers[q["key"]])
            data[q["key"]][key] = data[q["key"]].get(key, 0) + 1

        data["total_votes"] += 1
        save_data(data)

    return wins


st.set_page_config(page_title="Yes/No Poll", page_icon="\U0001F5F3️")
st.title("Poll Time")

data = load_data()

# Stored in the URL (not just session state) so reloading the page keeps
# showing results instead of sending you back to the quiz.
show_results = "done" in st.query_params

if not show_results:
    st.subheader("Questions")
    answers = {}
    for q in QUESTIONS:
        answers[q["key"]] = render_question(q)

    if st.button("Submit answers"):
        st.session_state["wins"] = record_vote(answers)
        st.query_params["done"] = "1"
        st.rerun()

if show_results:
    st.divider()
    st.subheader("Results so far")

    wins = st.session_state.pop("wins", None)
    if wins:
        for q in QUESTIONS:
            if q["key"] in wins:
                if wins[q["key"]]:
                    st.balloons()
                    st.success(f"You won on \"{q['text']}\"!")
                else:
                    st.warning(f"No luck on \"{q['text']}\" this time.")

    for q in QUESTIONS:
        counts = data[q["key"]]
        total = sum(counts.values())
        st.markdown(f"**{q['text']}**")
        if total == 0:
            st.caption("No answers yet.")
            continue

        if q["type"] in ("yesno", "choice"):
            for option, count in counts.items():
                pct = round(count / total * 100)
                st.progress(pct / 100, text=f"{option}: {pct}%  ({count})")

        elif q["type"] == "scale":
            avg = sum(int(k) * v for k, v in counts.items()) / total
            st.caption(f"Average: {avg:.1f} / {q['max']}  ·  {total} ratings")

            if q.get("show_distribution"):
                xs = list(range(q["min"], q["max"] + 1))
                ys = [counts[str(x)] for x in xs]
                chart_df = pd.DataFrame({"rating": xs, "responses": smooth(ys)}).set_index("rating")
                st.line_chart(chart_df)

        elif q["type"] == "number":
            xs = list(range(q["min"], q["max"] + 1))
            chart_df = pd.DataFrame({"number": xs, "picks": [counts[str(x)] for x in xs]}).set_index("number")
            st.bar_chart(chart_df)

    st.caption(f"Total votes: {data['total_votes']}")

    if st.button("Vote again"):
        del st.query_params["done"]
        st.rerun()
