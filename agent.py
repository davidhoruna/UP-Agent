__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')


from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ConversationBufferMemory
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
import logging
import os
import glob
from pathlib import Path



logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UPAgent:
    def __init__(self, api_key: str, pdf_directory: str):
        self.api_key = api_key
        
        # Initialize LLM
        self.llm = ChatOpenAI(
            api_key=api_key,
            model_name="gpt-4-turbo-preview",
            temperature=0.7
        )
        
        # Initialize vector store
        self.vector_store = self._initialize_vector_store(pdf_directory)
        
        # Initialize memory
        self.memory = ConversationBufferMemory(
            return_messages=True,
            memory_key="chat_history"
        )

        # System prompt
        self.system_prompt = """Eres Agente UP, un asistente especializado de la Universidad del Pacífico.
        Tu función es ayudar a estudiantes a encontrar y entender información sobre los reglamentos universitarios.

        IMPORTANTE:
        - SIEMPRE identifícate como "Agente UP" y mantén un tono profesional pero amigable
        - SIEMPRE cita las fuentes específicas de donde obtienes la información
        - SIEMPRE basa tus respuestas ÚNICAMENTE en la información proporcionada en el contexto y documentos pdf subidos por el usuario
        - Si la información no está en el contexto, indícalo claramente
        - Estructura tus respuestas de manera clara y organizada"""

    def _initialize_vector_store(self, pdf_directory: str) -> Chroma:
        """Initialize vector store with PDF documents"""
        try:
            embeddings = OpenAIEmbeddings(openai_api_key=self.api_key)
            vector_store = Chroma(
                persist_directory="chroma_db",
                embedding_function=embeddings
            )

            # Load PDFs if store is empty
            if not vector_store._collection.count():
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=1000,
                    chunk_overlap=200
                )
                
                for pdf_path in glob.glob(os.path.join(pdf_directory, "*.pdf")):
                    loader = PyPDFLoader(pdf_path)
                    documents = loader.load()
                    chunks = text_splitter.split_documents(documents)
                    # Add source filename to metadata
                    for chunk in chunks:
                        chunk.metadata["source"] = Path(pdf_path).name
                    vector_store.add_documents(chunks)
                vector_store.persist()

            return vector_store

        except Exception as e:
            logger.error(f"Error initializing vector store: {e}")
            raise

    def process_message(self, message: str) -> str:
        """Process user message and return response"""
        try:
            # Search relevant documents
            docs = self.vector_store.similarity_search(message)
            
            # Format context with sources
            context_parts = []
            for doc in docs:
                source = doc.metadata.get("source", "Documento sin especificar")
                page = doc.metadata.get("page", "página no especificada")
                context_parts.append(f"[Fuente: {source}, Página: {page}]\n{doc.page_content}")
            
            context = "\n\n".join(context_parts)

            # Create prompt with context
            prompt = ChatPromptTemplate.from_messages([
                ("system", self.system_prompt),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", f"""Contexto del reglamento:
                {context}
                
                Pregunta del usuario: {message}
                
                Responde como Agente UP, citando las fuentes específicas (documento y página).""")
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
            return "Lo siento, hubo un error al procesar tu consulta. Por favor, intenta de nuevo."

def main():
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY no está configurada")

        bot = UPAgent(api_key, "pdfs")

        print("¡Hola! Soy Agente UP, especialista en reglamentos de la Universidad del Pacífico.")
        print("Estoy aquí para ayudarte a encontrar y entender información sobre los reglamentos.")
        print("Escribe 'salir' para terminar.")

        while True:
            user_input = input("\nTú: ").strip()
            if user_input.lower() in ['salir', 'exit', 'adiós']:
                print("\nBot: ¡Hasta luego! Si tienes más preguntas sobre los reglamentos, no dudes en consultarme.")
                break

            response = bot.process_message(user_input)
            print(f"\nBot: {response}")

    except KeyboardInterrupt:
        print("\nBot: Sesión terminada.")
    except Exception as e:
        logger.error(f"Error: {e}")
        print("Error al iniciar el sistema. Verifica la configuración.")



if __name__ == "__main__":
    main()

