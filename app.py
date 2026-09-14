import json
import os

import streamlit as st

DATA_FILE = "totals.json"

# Edit this list to change the questions. Each key must be unique.
QUESTIONS = [
    {"key": "pineapple_pizza", "text": "Do you like pineapple on pizza?"},
    {"key": "morning_person", "text": "Are you a morning person?"},
    {"key": "cats_over_dogs", "text": "Do you prefer cats over dogs?"},
    {"key": "hot_dog_sandwich", "text": "Is a hot dog a sandwich?"},
    {"key": "toilet_paper_over", "text": "Should toilet paper go over the roll?"},
]


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
    else:
        data = {}

    # Fill in any missing questions/voters so the file stays easy to hand-edit.
    for q in QUESTIONS:
        data.setdefault(q["key"], {"yes": 0, "no": 0})
    data.setdefault("voters", [])
    return data


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


st.set_page_config(page_title="Yes/No Poll", page_icon="\U0001F5F3️")
st.title("Yes/No Poll")

data = load_data()

st.subheader("Login")
name = st.text_input("Enter your name to vote")

already_voted = name.strip().lower() in [v.lower() for v in data["voters"]] if name.strip() else False

if name.strip() and already_voted:
    st.info(f"Looks like **{name}** already voted. Thanks for participating!")
elif name.strip():
    st.subheader("Questions")
    answers = {}
    for q in QUESTIONS:
        answers[q["key"]] = st.radio(q["text"], ["Yes", "No"], horizontal=True, key=q["key"])

    if st.button("Submit answers"):
        for q in QUESTIONS:
            choice = "yes" if answers[q["key"]] == "Yes" else "no"
            data[q["key"]][choice] += 1
        data["voters"].append(name.strip())
        save_data(data)
        st.success("Thanks! Your answers were recorded.")
        st.rerun()
else:
    st.caption("Enter your name above to answer the questions.")

st.divider()
st.subheader("Results so far")

for q in QUESTIONS:
    yes = data[q["key"]]["yes"]
    no = data[q["key"]]["no"]
    total = yes + no
    st.markdown(f"**{q['text']}**")
    if total == 0:
        st.caption("No answers yet.")
    else:
        yes_pct = round(yes / total * 100)
        no_pct = 100 - yes_pct
        st.progress(yes_pct / 100, text=f"Yes: {yes_pct}%  |  No: {no_pct}%  ({total} votes)")

st.caption(f"Total voters: {len(data['voters'])}")
