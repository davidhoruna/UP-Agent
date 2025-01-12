import streamlit as st
import os
from dotenv import load_dotenv
from agent import UPAgent

# Load environment variables
load_dotenv()

# Page config
st.set_page_config(page_title="Research Assistant", page_icon="🔍")
st.title("Research Assistant")

# Initialize session state
if "agent" not in st.session_state:
    st.session_state.agent = ResearchAgent(os.getenv("OPENAI_API_KEY"))
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Ask a question"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        response = st.session_state.agent.query(prompt)
        st.markdown(response)
    st.session_state.messages.append({"role": "assistant", "content": response})

# Sidebar - PDF file uploader
with st.sidebar:
    st.header("Upload PDFs")
    uploaded_files = st.file_uploader("Upload your PDFs", accept_multiple_files=True, type='pdf')
    
    if uploaded_files:
        for file in uploaded_files:
            with open(f"pdfs/{file.name}", "wb") as f:
                f.write(file.getvalue())
        st.success("PDFs uploaded successfully! Please refresh the page.")

    st.header("Options")
    if st.button("Clear Conversation"):
        st.session_state.messages = []
        st.rerun()