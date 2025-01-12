
#%%
from langchain.tools import DuckDuckGoSearchRun
from langchain.document_loaders import DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from langchain.chat_models import ChatOpenAI
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from langchain.agents import initialize_agent, Tool
from langchain.agents import AgentType
#%%
class UPAgent:
    def __init__(self, openai_api_key):
        self.llm = ChatOpenAI(openai_api_key=openai_api_key)
        self.embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)
        self.memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
        
        # Initialize PDF Knowledge Base
        self.pdf_knowledge = self._init_pdf_knowledge()
        
        # Initialize Tools
        search = DuckDuckGoSearchRun()
        self.tools = [
            Tool(
                name="PDF Knowledge Base",
                func=self._query_pdfs,
                description="Use this to answer questions about content in the PDF documents"
            ),
            Tool(
                name="Web Search",
                func=search.run,
                description="Use this to search the internet for recent or additional information"
            )
        ]
        
        # Initialize Agent
        self.agent = initialize_agent(
            self.tools,
            self.llm,
            agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
            memory=self.memory,
            verbose=True
        )
    
    def _init_pdf_knowledge(self):
        loader = DirectoryLoader('pdfs/', glob="*.pdf")
        documents = loader.load()
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        texts = text_splitter.split_documents(documents)
        return Chroma.from_documents(texts, self.embeddings)
    
    def _query_pdfs(self, query):
        docs = self.pdf_knowledge.similarity_search(query)
        return "\n".join([doc.page_content for doc in docs])
    
    def query(self, question):
        return self.agent.run(question)