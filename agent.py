from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import SystemMessage, HumanMessage
from langchain.memory import ConversationBufferMemory
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
import logging
import os
import glob
from pathlib import Path
import shutil

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class UPAgent:
    def __init__(self, api_key: str, pdf_directory: str):
        """Initialize UP Agent with API key and PDF directory"""
        self.api_key = api_key
        self.pdf_directory = Path(pdf_directory)
        
        # Ensure PDF directory exists
        self.pdf_directory.mkdir(exist_ok=True)
        
        # Initialize components
        self.llm = self._initialize_llm()
        self.vector_store = self._initialize_vector_store()
        self.memory = self._initialize_memory()

    def _initialize_llm(self):
        """Initialize the language model"""
        return ChatOpenAI(
            api_key=self.api_key,
            model_name="gpt-4-turbo-preview",
            temperature=0.7
        )

    def _initialize_memory(self):
        """Initialize conversation memory"""
        return ConversationBufferMemory(
            return_messages=True,
            memory_key="chat_history"
        )

    def _initialize_vector_store(self) -> Chroma:
        """Initialize and load the vector store"""
        try:
            embeddings = OpenAIEmbeddings(openai_api_key=self.api_key)
            vector_store = Chroma(
                persist_directory="chroma_db",
                embedding_function=embeddings,
                collection_name="up_docs"
            )

            # Load PDFs only if the vector store is empty
            if vector_store._collection.count() == 0:
                pdf_files = list(self.pdf_directory.glob("*.pdf"))
                if pdf_files:
                    logger.info(f"Loading {len(pdf_files)} PDF files...")
                    self._load_pdfs(vector_store, pdf_files)

            return vector_store

        except Exception as e:
            logger.error(f"Error initializing vector store: {e}")
            raise

    def _load_pdfs(self, vector_store, pdf_files):
        """Load PDFs into the vector store"""
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        
        for pdf_path in pdf_files:
            try:
                logger.info(f"Processing {pdf_path.name}")
                loader = PyPDFLoader(str(pdf_path))
                documents = loader.load()
                chunks = text_splitter.split_documents(documents)
                
                # Add metadata
                for chunk in chunks:
                    chunk.metadata["source"] = pdf_path.name
                
                vector_store.add_documents(chunks)
                
            except Exception as e:
                logger.error(f"Error processing {pdf_path.name}: {e}")

        vector_store.persist()

    def process_message(self, message: str) -> str:
        """Process user message and return response"""
        try:
            # Check if we have any documents loaded
            if not self.vector_store._collection.count():
                return ("No hay documentos cargados en el sistema. "
                       "Por favor, carga algunos PDFs para poder responder consultas.")

            # Search relevant documents
            docs = self.vector_store.similarity_search(message)
            
            # Format context with sources
            context_parts = []
            for doc in docs:
                source = doc.metadata.get("source", "Documento sin especificar")
                page = doc.metadata.get("page", "página no especificada")
                context_parts.append(f"[Fuente: {source}, Página: {page}]\n{doc.page_content}")
            
            context = "\n\n".join(context_parts)

            # Create prompt
            prompt = ChatPromptTemplate.from_messages([
                ("system", self._get_system_prompt()),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", f"Contexto del reglamento:\n{context}\n\n"
                         f"Pregunta del usuario: {message}\n\n"
                         "Responde como Agente UP, citando las fuentes específicas.")
            ])

            # Get response
            response = prompt.invoke({
                "chat_history": self.memory.chat_memory.messages
            }).to_messages()

            # Get LLM response
            llm_response = self.llm.invoke(response)
            
            # Update memory
            self.memory.chat_memory.add_user_message(message)
            self.memory.chat_memory.add_ai_message(llm_response.content)

            return llm_response.content

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return ("Lo siento, hubo un error al procesar tu consulta. "
                   "Por favor, intenta de nuevo.")

    def _get_system_prompt(self):
        """Get the system prompt for the agent"""
        return """Eres Agente UP, un asistente especializado de la Universidad del Pacífico.
        Tu función es ayudar a estudiantes a encontrar y entender información sobre los reglamentos universitarios.

        IMPORTANTE:
        - SIEMPRE identifícate como "Agente UP" y mantén un tono profesional pero amigable
        - SIEMPRE cita las fuentes específicas de donde obtienes la información
        - SIEMPRE basa tus respuestas ÚNICAMENTE en la información proporcionada en el contexto
        - Si la información no está en el contexto, indícalo claramente
        - Estructura tus respuestas de manera clara y organizada"""