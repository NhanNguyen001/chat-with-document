import os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Load environment variables
load_dotenv()


class VectorStore:
    def __init__(self, persist_directory="db"):
        # Get API key from environment
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")

        self.embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)
        self.persist_directory = persist_directory

    def create_vector_store(self, documents):
        """
        Create a vector store from documents
        """
        if not documents:
            raise ValueError("No documents provided")

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=200, length_function=len
        )
        splits = text_splitter.split_documents(documents)

        return Chroma.from_documents(
            documents=splits,
            embedding=self.embeddings,
            persist_directory=self.persist_directory,
        )
