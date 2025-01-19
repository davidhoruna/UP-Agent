from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import SystemMessage, HumanMessage
from langchain.memory import ConversationBufferMemory
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from blackboard_scraper import BlackboardScraper
from calendar_manager import CalendarManager
import logging
import os
import glob
from pathlib import Path
import re
from datetime import datetime


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
        self.calendar = CalendarManager()

        self.date_parsers = [
            ('%d/%m/%Y', r'\d{1,2}/\d{1,2}/\d{4}'),
            ('%d de %B del %Y', r'\d{1,2} de [a-zA-Z]+ del \d{4}'),
            ('%d de %B de %Y', r'\d{1,2} de [a-zA-Z]+ de \d{4}'),
            ('%Y-%m-%d', r'\d{4}-\d{2}-\d{2}')
        ]
        self.spanish_months = {
            'enero': 'January', 'febrero': 'February', 'marzo': 'March',
            'abril': 'April', 'mayo': 'May', 'junio': 'June',
            'julio': 'July', 'agosto': 'August', 'septiembre': 'September',
            'octubre': 'October', 'noviembre': 'November', 'diciembre': 'December'
        }



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
            
            # Configuración para Chroma 0.5.x
            vector_store = Chroma(
                persist_directory="chroma_db",
                embedding_function=embeddings,
                collection_name="up_docs",
                # Los nuevos parámetros de Chroma 0.5
                collection_metadata={
                    "hnsw:space": "cosine",
                    "hnsw:construction_policy": "best_effort"
                }
            )

            # Load PDFs only if the vector store is empty
            collection_size = vector_store._collection.count()
            if collection_size == 0:
                pdf_files = list(self.pdf_directory.glob("*.pdf"))
                if pdf_files:
                    logger.info(f"Loading {len(pdf_files)} PDF files...")
                    self._load_pdfs(vector_store, pdf_files)
                else:
                    logger.warning("No PDF files found in directory")
            else:
                logger.info(f"Using existing vector store with {collection_size} documents")

            return vector_store

        except Exception as e:
            logger.error(f"Error initializing vector store: {e}")
            raise

    def _load_pdfs(self, vector_store, pdf_files):
        """Load PDFs into the vector store"""
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            is_separator_regex=False
        )
        
        for pdf_path in pdf_files:
            try:
                logger.info(f"Processing {pdf_path.name}")
                loader = PyPDFLoader(str(pdf_path))
                documents = loader.load()
                chunks = text_splitter.split_documents(documents)
                
                # Enhanced metadata
                for chunk in chunks:
                    chunk.metadata.update({
                        "source": pdf_path.name,
                        "file_path": str(pdf_path),
                        "chunk_size": len(chunk.page_content),
                        "processed_date": str(Path(pdf_path).stat().st_mtime)
                    })
                
                vector_store.add_documents(chunks)
                logger.info(f"Added {len(chunks)} chunks from {pdf_path.name}")
                
            except Exception as e:
                logger.error(f"Error processing {pdf_path.name}: {e}")

        vector_store.persist()
        logger.info("Vector store persisted successfully")


    def _parse_date(self, date_str: str) -> datetime:
        """Parse date string using multiple formats"""
        date_str = date_str.lower()
        
        # Replace Spanish month names
        for es, en in self.spanish_months.items():
            date_str = date_str.replace(es, en)
        
        # Try each date format
        for fmt, _ in self.date_parsers:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        raise ValueError(f"Unable to parse date: {date_str}")
    
    def _extract_evaluation_dates_from_syllabus(self, course_name: str) -> list:
        """Extract evaluation dates with improved pattern matching"""
        try:
            # Search for evaluation-related content
            query = f"evaluación cronograma {course_name}"
            docs = self.vector_store.similarity_search(query, k=5)
            
            evaluations = []
            eval_patterns = [
                r'(evaluación|examen|práctica|parcial|final|control|quiz|exposición|proyecto)',
                r'(\d{1,2}%|\d{1,2} %)',  # Match percentage weights
                r'(virtual|presencial|oral|escrito)'  # Match evaluation modalities
            ]
            
            for doc in docs:
                content = doc.page_content.lower()
                
                # Find evaluation sections
                for section in re.split(r'\n{2,}', content):
                    if any(word in section for word in ['evaluación', 'examen', 'práctica']):
                        # Extract evaluation details
                        eval_info = {
                            'course': course_name,
                            'type': '',
                            'date': None,
                            'weight': None,
                            'modality': None,
                            'source': doc.metadata.get('source', 'Unknown'),
                            'page': doc.metadata.get('page', 'N/A')
                        }
                        
                        # Extract evaluation type
                        for type_match in re.finditer(eval_patterns[0], section, re.IGNORECASE):
                            eval_info['type'] = type_match.group(0).capitalize()
                            
                            # Look for date near the evaluation type
                            nearby_text = section[max(0, type_match.start()-100):min(len(section), type_match.end()+100)]
                            
                            # Search for dates
                            for _, date_pattern in self.date_parsers:
                                date_match = re.search(date_pattern, nearby_text)
                                if date_match:
                                    try:
                                        eval_info['date'] = self._parse_date(date_match.group(0))
                                        break
                                    except ValueError:
                                        continue
                            
                            # Extract weight
                            weight_match = re.search(r'(\d{1,2})\s*%', nearby_text)
                            if weight_match:
                                eval_info['weight'] = int(weight_match.group(1))
                            
                            # Extract modality
                            modality_match = re.search(eval_patterns[2], nearby_text)
                            if modality_match:
                                eval_info['modality'] = modality_match.group(0).capitalize()
                        
                        if eval_info['date']:
                            evaluations.append(eval_info)
            
            return evaluations
        
        except Exception as e:
            logger.error(f"Error extracting evaluation dates: {e}")
            return []

    def _schedule_course_evaluations(self, course_name: str) -> str:
        evaluations = self._extract_evaluation_dates_from_syllabus(course_name)
        
        if not evaluations:
            return f"No encontré fechas de evaluación para {course_name}. Verifica que el sílabo esté cargado."
        
        scheduled = []
        errors = []
        
        for eval_info in evaluations:
            try:
                date = eval_info['date']
                title_parts = [
                    f"{course_name}",
                    f"{eval_info['type']}"
                ]
                if eval_info['weight']:
                    title_parts.append(f"({eval_info['weight']}%)")
                
                description_parts = [
                    f"Tipo: {eval_info['type']}",
                    f"Modalidad: {eval_info['modality'] or 'No especificada'}",
                    f"Peso: {eval_info['weight']}%" if eval_info['weight'] else None,
                    f"Fuente: {eval_info['source']}, Página: {eval_info['page']}"
                ]
                
                success, result = self.calendar.add_event(
                    title=" - ".join(title_parts),
                    description="\n".join(filter(None, description_parts)),
                    start_time=date.replace(hour=10),  # Default to 10 AM
                    duration_hours=2  # Default duration
                )
                
                if success:
                    scheduled.append(f"✅ {eval_info['type']} ({date.strftime('%d/%m/%Y')})")
                else:
                    errors.append(f"❌ {eval_info['type']}: {result}")
                    
            except Exception as e:
                errors.append(f"❌ Error con {eval_info['type']}: {str(e)}")
        
        response_parts = [f"📅 {course_name}:"]
        if scheduled:
            response_parts.extend(scheduled)
        if errors:
            response_parts.extend(["\nErrores:", *errors])
        
        return "\n".join(response_parts)

    def process_message(self, message: str) -> str:
        """Process user message and return response"""
        try:
            # Check for calendar-related intents
            if "agenda" in message.lower() and ("evaluaciones" or "examenes") in message.lower():
                # Extraer nombre del curso
                course_match = re.search(r'(?:para|de|del curso)\s+([^,\.]+)', message, re.IGNORECASE)
                if course_match:
                    course_name = course_match.group(1).strip()
                    return self._schedule_course_evaluations(course_name)
                else:
                    return "Por favor, especifica el nombre del curso del cual quieres agendar las evaluaciones."

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
        Tu función es ayudar a estudiantes a encontrar, manejar y entender información universitaria.

        IMPORTANTE:
        - SIEMPRE identifícate como "Agente UP" y mantén un tono profesional pero amigable
        - SIEMPRE cita las fuentes específicas de donde obtienes la información
        - SIEMPRE basa tus respuestas ÚNICAMENTE en la información proporcionada en el contexto
        - Tienes acceso a los materiales de los cursos a través de Blackboard. El usuario puede conectar sus archivos de blackboard
        a través del botón en el panel de opciones.
        - Puedes agendar eventos (exámenes, evaluaciones, etc) via Google Calendar api cuando el usuario lo pida.
        - Estructura tus respuestas de manera clara y organizada"""