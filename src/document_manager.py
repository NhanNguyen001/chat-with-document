import os
import shutil
from typing import List
from .document_loaders import DocumentLoader


class DocumentManager:
    def __init__(self, documents_dir: str):
        self.documents_dir = documents_dir
        os.makedirs(documents_dir, exist_ok=True)

    def upload_document(self, file_path: str) -> bool:
        """
        Upload a document to the documents directory
        """
        try:
            filename = os.path.basename(file_path)
            destination = os.path.join(self.documents_dir, filename)
            shutil.copy2(file_path, destination)
            return True
        except Exception as e:
            print(f"Error uploading document: {str(e)}")
            return False

    def load_documents(self) -> List:
        """
        Load all documents from the documents directory
        """
        documents = []

        for filename in os.listdir(self.documents_dir):
            file_path = os.path.join(self.documents_dir, filename)
            file_type = os.path.splitext(filename)[1].lower()

            try:
                docs = DocumentLoader.load_document(file_path, file_type)
                documents.extend(docs)
            except Exception as e:
                print(f"Error loading {filename}: {str(e)}")

        return documents
