from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader, PDFMinerLoader
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_openai import ChatOpenAI
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
import os
from dotenv import load_dotenv
import time
from langchain.schema import Document

# Load environment variables
load_dotenv()

class DocumentChatbot:
    def __init__(self, documents_dir="documents/"):
        self.documents_dir = documents_dir
        self.persist_directory = "chroma_db"
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        self.embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
        os.makedirs(self.persist_directory, exist_ok=True)
        self.setup_chain()
        
    def load_documents(self):
        """Load and process documents from the documents directory"""
        documents = []
        print(f"Scanning directory: {self.documents_dir}")
        print(f"Directory exists: {os.path.exists(self.documents_dir)}")
        print(f"Directory contents: {os.listdir(self.documents_dir)}")
        
        for filename in os.listdir(self.documents_dir):
            file_path = os.path.join(self.documents_dir, filename)
            print(f"Processing file: {filename}")
            print(f"Full file path: {file_path}")
            print(f"File exists: {os.path.exists(file_path)}")
            print(f"File size: {os.path.getsize(file_path)} bytes")
            
            try:
                if filename.endswith('.pdf'):
                    print(f"Loading PDF file: {filename}")
                    try:
                        # Verify PDF file header
                        with open(file_path, 'rb') as f:
                            header = f.read(4)
                            if header != b'%PDF':
                                print(f"Warning: {filename} does not appear to be a valid PDF file")
                                continue
                        
                        # Use PDFMinerLoader with default settings
                        loader = PDFMinerLoader(file_path)
                        print("Created PDFMinerLoader")
                        
                        loaded_docs = loader.load()
                        print(f"Loaded {len(loaded_docs)} pages")
                        
                        # Validate content
                        valid_docs = []
                        for doc in loaded_docs:
                            if hasattr(doc, 'page_content') and doc.page_content.strip():
                                valid_docs.append(doc)
                                print(f"Found valid content in document: {len(doc.page_content)} characters")
                                # Print first 100 characters to verify content
                                print(f"Content preview: {doc.page_content[:100]}...")
                        
                        if valid_docs:
                            print(f"Successfully loaded {len(valid_docs)} pages with content from {filename}")
                            documents.extend(valid_docs)
                        else:
                            print(f"Warning: No valid content found in {filename}")
                            
                    except Exception as pdf_error:
                        print(f"Error loading PDF {filename}: {str(pdf_error)}")
                        print(f"PDF Exception type: {type(pdf_error)}")
                        import traceback
                        print(f"PDF Traceback: {traceback.format_exc()}")
                        continue
                else:
                    print(f"Loading text file: {filename}")
                    loader = TextLoader(file_path)
                    loaded_docs = loader.load()
                    print(f"Successfully loaded text from {filename}")
                    documents.extend(loaded_docs)
            except Exception as e:
                print(f"Error loading {filename}: {str(e)}")
                print(f"Exception type: {type(e)}")
                import traceback
                print(f"Traceback: {traceback.format_exc()}")
                continue
                
        print(f"Total documents loaded: {len(documents)}")
        if not documents:
            print("Warning: No documents were successfully loaded")
            raise ValueError("No documents could be loaded successfully")
        return documents

    def process_documents(self, documents):
        """Process documents into text chunks"""
        all_texts = []
        print(f"Processing {len(documents)} documents for text extraction")
        for i, doc in enumerate(documents):
            try:
                if hasattr(doc, 'page_content'):
                    text = doc.page_content
                    print(f"Document {i+1}: Found page_content attribute")
                else:
                    text = str(doc)
                    print(f"Document {i+1}: Converting to string")
                
                if not text.strip():
                    print(f"Document {i+1}: Empty text content")
                    continue
                    
                print(f"Document {i+1}: Splitting text of length {len(text)}")
                chunks = self.text_splitter.split_text(text)
                print(f"Document {i+1}: Created {len(chunks)} chunks")
                # Convert chunks to Document objects
                doc_chunks = [Document(page_content=chunk) for chunk in chunks]
                all_texts.extend(doc_chunks)
            except Exception as e:
                print(f"Error processing document {i+1}: {str(e)}")
                continue
                
        print(f"Total chunks created: {len(all_texts)}")
        if not all_texts:
            print("Warning: No text content was extracted from documents")
            raise ValueError("No text content could be extracted from documents")
        return all_texts

    def create_vector_store(self, texts):
        """Create vector store from processed text chunks"""
        try:
            if not texts:
                raise ValueError("No texts to process")
                
            # Create a unique collection name
            collection_name = f"collection_{int(time.time())}"
            
            # Create vector store using Chroma with persistence
            vector_store = Chroma.from_documents(
                documents=texts,  # texts are now Document objects
                embedding=self.embeddings,
                collection_name=collection_name,
                persist_directory=self.persist_directory
            )
            
            # Persist the vector store
            vector_store.persist()
            print(f"Vector store persisted to {self.persist_directory}")
            
            return vector_store
        except Exception as e:
            print(f"Error creating vector store: {str(e)}")
            raise
        
    def setup_chain(self):
        """Initialize the chat chain with processed documents"""
        try:
            documents = self.load_documents()
            if not documents:
                print("No documents found")
                return
            
            print(f"Processing {len(documents)} documents...")
            texts = self.process_documents(documents)
            
            if not texts:
                print("No text content extracted from documents")
                return
            
            print(f"Creating vector store from {len(texts)} text chunks...")
            self.vectorstore = self.create_vector_store(texts)
            
            openai_api_key = os.getenv("OPENAI_API_KEY")
            if not openai_api_key:
                raise ValueError("OPENAI_API_KEY not found in environment variables")
            
            # Initialize memory
            self.memory = ConversationBufferMemory(
                memory_key="chat_history",
                return_messages=True,
                output_key="answer"
            )
                
            self.chain = ConversationalRetrievalChain.from_llm(
                llm=ChatOpenAI(
                    temperature=0,
                    model_name="gpt-3.5-turbo",
                    openai_api_key=openai_api_key
                ),
                retriever=self.vectorstore.as_retriever(
                    search_kwargs={"k": 3}
                ),
                memory=self.memory,
                return_source_documents=True,
                output_key="answer"
            )
            print("Chat chain setup complete")
        except Exception as e:
            print(f"Error in setup_chain: {str(e)}")
            raise
        
    def chat(self, query: str) -> str:
        """Process a user query and return the response"""
        if not hasattr(self, 'chain'):
            raise ValueError("Chat chain not initialized. Please upload some documents first.")
        try:
            result = self.chain({
                "question": query,
                "chat_history": self.memory.chat_memory.messages if hasattr(self, 'memory') else []
            })
            return result["answer"]
        except Exception as e:
            print(f"Error in chat: {str(e)}")
            raise 