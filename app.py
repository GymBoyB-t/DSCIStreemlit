import json
import os
import string
import threading

import streamlit as st

DATA_FILE = "totals.json"

_data_lock = threading.Lock()

QUESTIONS = [
    {
        "key": "marriage_age",
        "text": "What is the ideal age to get married?",
        "type": "number",
        "min": 1,
        "max": 100,
    },
    {
        "key": "hole_food",
        "text": "Name a food with a hole in it",
        "type": "text",
    },
    {
        "key": "pick_number",
        "text": "Pick a number 1-10",
        "type": "number",
        "min": 1,
        "max": 10,
    },
    {
        "key": "purple_thing",
        "text": "Name something purple",
        "type": "text",
    },
    {
        "key": "class_person",
        "text": "Name a person in this class",
        "type": "text",
    },
    {
        "key": "hot_or_cold",
        "text": "Would you rather be too hot or too cold?",
        "type": "choice",
        "options": ["Too hot", "Too cold"],
    },
    {
        "key": "dog_name",
        "text": "What is the most common dog name?",
        "type": "text",
    },
    {
        "key": "best_sport",
        "text": "What is the best sport?",
        "type": "text",
    },
]

_PUNCT_TABLE = str.maketrans("", "", string.punctuation)


def normalize_text(answer):
    cleaned = answer.strip().lower().translate(_PUNCT_TABLE)
    return " ".join(cleaned.split())


def default_counts(q):
    if q["type"] == "text":
        return {}
    if q["type"] == "choice":
        return {opt: 0 for opt in q["options"]}
    return {str(i): 0 for i in range(q["min"], q["max"] + 1)}  # number


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
    if q["type"] == "text":
        return st.text_input(q["text"], key=q["key"])
    if q["type"] == "choice":
        return st.radio(q["text"], q["options"], horizontal=True, key=q["key"])
    if q["type"] == "number":
        default = (q["min"] + q["max"]) // 2
        return st.number_input(
            q["text"], min_value=q["min"], max_value=q["max"], value=default, step=1, key=q["key"]
        )


def counts_key_for(q, answer):
    if q["type"] == "text":
        return normalize_text(answer)
    if q["type"] == "choice":
        return answer
    return str(int(answer))  # number


def majority_keys(counts):
    if not counts or sum(counts.values()) == 0:
        return set()
    top = max(counts.values())
    return {k for k, v in counts.items() if v == top}


def record_vote(answers):
    keyed = {q["key"]: counts_key_for(q, answers[q["key"]]) for q in QUESTIONS}
    with _data_lock:
        # Re-read the data and lock it untill were done with it
        data = load_data()
        for q in QUESTIONS:
            key = keyed[q["key"]]
            data[q["key"]][key] = data[q["key"]].get(key, 0) + 1
        data["total_votes"] += 1
        save_data(data)
    return keyed


def compute_score(user_keyed, data):
    score = 0
    for q in QUESTIONS:
        if user_keyed.get(q["key"]) in majority_keys(data[q["key"]]):
            score += 1
    return score


st.set_page_config(page_title="Poll Time", page_icon="\U0001F5F3️")
st.title("Poll Time")

data = load_data()

# Stored in the URL (not just session state) so reloading the page keeps
# showing results (and your score) instead of sending you back to the quiz.
show_results = "done" in st.query_params
user_keyed = {}
if show_results:
    try:
        user_keyed = json.loads(st.query_params.get("answers", "{}"))
    except json.JSONDecodeError:
        user_keyed = {}
    score = compute_score(user_keyed, data)
    st.metric("Your score", f"{score} / {len(QUESTIONS)}")
    st.caption("Points are earned for each answer that matches the current majority.")

if not show_results:
    st.subheader("Questions")
    answers = {}
    for q in QUESTIONS:
        answers[q["key"]] = render_question(q)

    if st.button("Submit answers"):
        missing = [q["text"] for q in QUESTIONS if q["type"] == "text" and not answers[q["key"]].strip()]
        if missing:
            st.error("Please answer: " + ", ".join(missing))
        else:
            keyed = record_vote(answers)
            st.query_params["answers"] = json.dumps(keyed)
            st.query_params["done"] = "1"
            st.rerun()

if show_results:
    st.divider()
    st.subheader("Results so far")

    for q in QUESTIONS:
        counts = data[q["key"]]
        total = sum(counts.values())
        st.markdown(f"**{q['text']}**")
        if total == 0:
            st.caption("No answers yet.")
            continue

        for option, count in sorted(counts.items(), key=lambda kv: kv[1], reverse=True):
            if count == 0:
                continue
            label = option.title() if q["type"] == "text" else option
            pct = round(count / total * 100)
            st.progress(pct / 100, text=f"{label}: {pct}%  ({count})")

    st.caption(f"Total votes: {data['total_votes']}")

    if st.button("Vote again"):
        del st.query_params["done"]
        del st.query_params["answers"]
        st.rerun()
