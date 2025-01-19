import streamlit as st
import os
from dotenv import load_dotenv
from agent import UPAgent
from calendar_manager import CalendarManager
from blackboard_scraper import BlackboardScraper
from pathlib import Path

# Fix SQLite version issues
import sys
try:
    __import__('pysqlite3')
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass

# Load environment variables
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY") or st.secrets["OPENAI_API_KEY"]

# Initialize session state for credentials
if "bb_credentials" not in st.session_state:
    st.session_state.bb_credentials = None
if "calendar_auth" not in st.session_state:
    st.session_state.calendar_auth = None

# Page config
st.set_page_config(
    page_title="Agente UP",
    page_icon="🎓",
    layout="wide"
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
    st.session_state.agent = UPAgent(api_key, "pdfs")
if "messages" not in st.session_state:
    st.session_state.messages = []

# Header
col1, col2 = st.columns([1, 4])
with col1:
    st.image("logo.png", width=100)
with col2:
    st.title("🎓 Agente UP")
    st.markdown("### Pregunta tus dudas de la UP")

# Add this function at the top level of your app.py
def ensure_pdfs_directory():
    """Ensure the pdfs directory exists and has default documents if needed"""
    pdfs_dir = Path("pdfs")
    pdfs_dir.mkdir(exist_ok=True)
    
    # Check if directory is empty
    if not any(pdfs_dir.iterdir()):
        st.info("No hay documentos cargados. Por favor, sube algunos PDFs para comenzar.")
        return False
    return True

# Sidebar
with st.sidebar:
    st.header("🔧 Opciones")
    
    # Blackboard Integration
    with st.expander("🎓 Blackboard"):
        if not st.session_state.bb_credentials:
            st.subheader("Conectar con Blackboard")
            bb_user = st.text_input("Usuario UP", key="bb_user")
            bb_pass = st.text_input("Contraseña", type="password", key="bb_pass")
            
            if st.button("Conectar a Blackboard"):
                try:
                    scraper = BlackboardScraper()
                    if scraper.login(bb_user, bb_pass):
                        st.session_state.bb_credentials = (bb_user, bb_pass)
                        st.success("✅ Conexión exitosa!")
                        
                        # Descargar archivos automáticamente
                        with st.spinner("Descargando archivos de cursos..."):
                            files_downloaded = scraper.download_course_files()
                            
                            if files_downloaded == 0:
                                st.warning("No hay archivos disponibles o error de descarga")
                            else:
                                st.success(f"📚 {files_downloaded} archivos descargados")
            
                            # Reinicializar el agente para incluir nuevos archivos
                                st.session_state.agent = UPAgent(api_key, "pdfs")

                    else:
                        st.error("❌ Error de autenticación")
                except Exception as e:
                    st.error(f"Error: {str(e)}")
        else:
            st.success("✅ Conectado a Blackboard")
            if st.button("Actualizar archivos"):
                with st.spinner("Actualizando archivos..."):
                    scraper = BlackboardScraper()
                    scraper.login(*st.session_state.bb_credentials)
                    files_updated = scraper.download_course_files()
                    st.success(f"📚 {files_updated} archivos actualizados")
                    st.session_state.agent = UPAgent(api_key, "pdfs")
            
            if st.button("Desconectar"):
                st.session_state.bb_credentials = None
                st.rerun()

    # Google Calendar Integration
    with st.expander("📅 Google Calendar"):
        if not st.session_state.calendar_auth:
            st.subheader("Conectar Google Calendar")
            
            if st.button("Autorizar Calendar"):
                try:
                    calendar = CalendarManager().authenticate()
                    if calendar:
                        st.session_state.calendar_auth = True
                        st.success("✅ Calendario conectado!")
                    else:
                        st.error("❌ Error de autenticación")
                except Exception as e:
                    st.error(f"Error: {str(e)}")
        else:
            st.success("✅ Calendario conectado")
            if st.button("Desconectar Calendar"):
                st.session_state.calendar_auth = None
                st.rerun()

    # Document Management
    with st.expander("📚 Documentos"):
        st.subheader("Cargar PDFs adicionales")
        uploaded_files = st.file_uploader(
            "Sube PDFs manualmente",
            accept_multiple_files=True,
            type='pdf'
        )
        
        if uploaded_files:
            with st.spinner("Procesando documentos..."):
                Path("pdfs").mkdir(exist_ok=True)
                for file in uploaded_files:
                    with open(f"pdfs/{file.name}", "wb") as f:
                        f.write(file.getvalue())
                st.session_state.agent = UPAgent(api_key, "pdfs")
                st.success("✅ Documentos procesados")

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




