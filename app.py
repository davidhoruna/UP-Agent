import streamlit as st
import os
from dotenv import load_dotenv
from agent import UPAgent
from pathlib import Path

# Load environment variables
load_dotenv()

# Page config
st.set_page_config(
    page_title="Agente UP",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS with UP colors
st.markdown("""
    <style>
        /* UP Colors */
        :root {
            --up-blue: #0088ff;
            --up-light-blue: #E3F2FD;
            --up-white: #FFFFFF;
        }

        /* Main container */
        .main {
            background-color: var(--up-white);
        }
        
        .stApp {
            max-width: 1200px;
            margin: 0 auto;
        }

        /* Headers */
        h1, h2, h3 {
            color: var(--up-blue) !important;
        }

        /* Chat messages */
        .chat-message {
            padding: 1.5rem;
            border-radius: 0.5rem;
            margin-bottom: 1rem;
            border: 1px solid #eee;
        }
        .chat-message.user {
            background-color: var(--up-light-blue);
        }
        .chat-message.assistant {
            background-color: var(--up-white);
            border-left: 4px solid var(--up-blue);
        }

        /* Buttons */
        .stButton button {
            background-color: var(--up-blue);
            color: var(--up-white);
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 0.3rem;
        }
        .stButton button:hover {
            background-color: #004d8f;
        }

        /* Sidebar */
        .css-1d391kg {
            background-color: var(--up-light-blue);
        }

        /* Input box */
        .stTextInput input {
            border: 2px solid var(--up-blue);
            border-radius: 0.5rem;
        }

        /* Dividers */
        hr {
            border-color: var(--up-blue);
        }

        /* Footer */
        .footer {
            background-color: var(--up-blue);
            color: var(--up-white);
            padding: 1rem;
            border-radius: 0.5rem;
            margin-top: 2rem;
        }
        
        /* Spinner */
        .stSpinner {
            border-top-color: var(--up-blue) !important;
        }
    </style>
""", unsafe_allow_html=True)

# Initialize session state
if "agent" not in st.session_state:
    st.session_state.agent = UPAgent(os.getenv("OPENAI_API_KEY"), "pdfs")
if "messages" not in st.session_state:
    st.session_state.messages = []

# Header
col1, col2 = st.columns([1, 4])
with col1:
    st.image("logo.png", width=100)
with col2:
    st.title("🎓 Agente UP")
    st.markdown("### Pregunta tus dudas de la UP")

# Sidebar
with st.sidebar:
    st.header("📚 Cargar Documentos")
    uploaded_files = st.file_uploader(
        "Sube tus PDFs",
        accept_multiple_files=True,
        type='pdf',
        help="Puedes subir múltiples archivos PDF"
    )
    
    if uploaded_files:
        with st.spinner("Procesando documentos..."):
            Path("pdfs").mkdir(exist_ok=True)
            for file in uploaded_files:
                with open(f"pdfs/{file.name}", "wb") as f:
                    f.write(file.getvalue())
            # Reinitialize agent with new PDFs
            st.session_state.agent = UPAgent(os.getenv("OPENAI_API_KEY"), "pdfs")
            st.success("¡Documentos cargados exitosamente!")
    
    st.header("⚙️ Opciones")
    if st.button("🗑️ Limpiar Conversación"):
        st.session_state.messages = []
        st.rerun()

# Main chat interface
st.markdown("---")

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Escribe tu pregunta aquí..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Get and display assistant response
    with st.chat_message("assistant"):
        with st.spinner("Pensando..."):
            response = st.session_state.agent.process_message(prompt)
            st.markdown(response)
    st.session_state.messages.append({"role": "assistant", "content": response})

# Footer
st.markdown("---")




