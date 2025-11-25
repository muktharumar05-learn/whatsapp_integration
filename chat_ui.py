import streamlit as st
import requests

API_URL = "http://localhost:8000/chat"

st.title("Chat with AI Agent")

if "session_id" not in st.session_state:
    st.session_state.session_id = None

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "user_input" not in st.session_state:
    st.session_state.user_input = ""

def send_message(user_message):
    payload = {"user_message": user_message}
    if st.session_state.session_id:
        payload["session_id"] = st.session_state.session_id

    response = requests.post(API_URL, json=payload)
    if response.status_code == 200:
        data = response.json()
        st.session_state.session_id = data["session_id"]
        return data["ai_reply"]
    else:
        return f"Error: {response.status_code} - {response.text}"

# Use st.form to wrap input and button to avoid rerun on each keypress
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Your message:", key="user_input")
    submit = st.form_submit_button("Send")

if submit and user_input.strip():
    user_message = user_input.strip()
    st.session_state.chat_history.append(("User", user_message))
    ai_reply = send_message(user_message)
    st.session_state.chat_history.append(("AI", ai_reply))
    # Clearing input happens automatically because of clear_on_submit=True in the form

# Display chat history
for sender, msg in st.session_state.chat_history:
    if sender == "User":
        st.markdown(f"**You:** {msg}")
    else:
        st.markdown(f"**Agent:** {msg}")
