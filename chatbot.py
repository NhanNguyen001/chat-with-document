import os
import shutil
from dotenv import load_dotenv
from langchain.document_loaders import (
    DirectoryLoader,
    PyPDFLoader,
    TextLoader,
    UnstructuredWordDocumentLoader,
    CSVLoader,
)
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from langchain.chat_models import ChatOpenAI
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory

# Load environment variables
load_dotenv()


class DocumentChatbot:
    def __init__(self, documents_dir="documents/"):
        self.documents_dir = documents_dir
        # Create documents directory if it doesn't exist
        os.makedirs(self.documents_dir, exist_ok=True)
        self.embeddings = OpenAIEmbeddings()
        self.setup_vectorstore()
        self.setup_chain()

    def upload_document(self, file_path: str) -> bool:
        """
        Upload a document to the documents directory and update the vector store
        """
        try:
            # Get the filename from the path
            filename = os.path.basename(file_path)

            # Copy file to documents directory
            destination = os.path.join(self.documents_dir, filename)
            shutil.copy2(file_path, destination)

            # Reload vector store with new document
            self.setup_vectorstore()
            return True
        except Exception as e:
            print(f"Error uploading document: {str(e)}")
            return False

    def setup_vectorstore(self):
        """
        Setup vector store with support for multiple file types
        """
        documents = []

        # Process each file in the documents directory
        for filename in os.listdir(self.documents_dir):
            file_path = os.path.join(self.documents_dir, filename)

            try:
                # Choose appropriate loader based on file extension
                if filename.endswith(".pdf"):
                    loader = PyPDFLoader(file_path)
                elif filename.endswith(".txt"):
                    loader = TextLoader(file_path)
                elif filename.endswith(".docx"):
                    loader = UnstructuredWordDocumentLoader(file_path)
                elif filename.endswith(".csv"):
                    loader = CSVLoader(file_path)
                else:
                    print(f"Unsupported file type: {filename}")
                    continue

                # Load documents
                documents.extend(loader.load())

            except Exception as e:
                print(f"Error loading {filename}: {str(e)}")
                continue

        if not documents:
            print(
                "No documents loaded. Please add documents to the documents directory."
            )
            return

        # Split documents into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=200, length_function=len
        )
        splits = text_splitter.split_documents(documents)

        # Create vector store
        self.vectorstore = Chroma.from_documents(
            documents=splits, embedding=self.embeddings, persist_directory="db"
        )

    def setup_chain(self):
        # Initialize language model
        # llm = ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0)
        llm = ChatOpenAI(model_name="gpt-4o", temperature=0)

        # Setup memory
        self.memory = ConversationBufferMemory(
            memory_key="chat_history", return_messages=True
        )

        # Create conversation chain
        self.chain = ConversationalRetrievalChain.from_llm(
            llm=llm,
            retriever=self.vectorstore.as_retriever(),
            memory=self.memory,
            return_source_documents=True,
        )

    def chat(self, query: str) -> str:
        """
        Process a user query and return the response
        """
        result = self.chain({"question": query})
        return result["answer"]


def main():
    # Create .env file with your OpenAI API key
    if not os.path.exists(".env"):
        with open(".env", "w") as f:
            f.write("OPENAI_API_KEY=your-api-key-here")
        print("Please add your OpenAI API key to the .env file")
        return

    # Initialize chatbot
    chatbot = DocumentChatbot()

    print("Chatbot initialized. Available commands:")
    print("- 'upload <file_path>': Upload a new document")
    print("- 'quit': Exit the chatbot")

    while True:
        user_input = input("You: ").strip()

        if user_input.lower() == "quit":
            break

        # Handle document upload command
        elif user_input.lower().startswith("upload "):
            file_path = user_input[7:].strip()  # Remove 'upload ' from the input
            if os.path.exists(file_path):
                success = chatbot.upload_document(file_path)
                if success:
                    print(f"Document uploaded successfully: {file_path}")
                else:
                    print("Failed to upload document")
            else:
                print(f"File not found: {file_path}")
            continue

        # Handle normal chat
        response = chatbot.chat(user_input)
        print(f"Bot: {response}")


if __name__ == "__main__":
    main()
