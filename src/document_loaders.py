from langchain.document_loaders import (
    PyPDFLoader,
    TextLoader,
    UnstructuredWordDocumentLoader,
    CSVLoader,
)


class DocumentLoader:
    @staticmethod
    def load_document(file_path: str, file_type: str):
        """
        Load a document based on its file type
        """
        loaders = {
            ".pdf": PyPDFLoader,
            ".txt": TextLoader,
            ".docx": UnstructuredWordDocumentLoader,
            ".csv": CSVLoader,
        }

        if file_type not in loaders:
            raise ValueError(f"Unsupported file type: {file_type}")

        loader = loaders[file_type](file_path)
        return loader.load()
