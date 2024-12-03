import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory

# Load environment variables
load_dotenv()


class ChatChain:
    def __init__(self, retriever):
        # Get API key from environment
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")

        self.llm = ChatOpenAI(
            model_name="gpt-3.5-turbo", temperature=0, openai_api_key=openai_api_key
        )
        self.memory = ConversationBufferMemory(
            memory_key="chat_history", return_messages=True, output_key="answer"
        )
        self.chain = self._create_chain(retriever)

    def _create_chain(self, retriever):
        return ConversationalRetrievalChain.from_llm(
            llm=self.llm,
            retriever=retriever,
            memory=self.memory,
            return_source_documents=True,
            output_key="answer",
        )

    def process_query(self, query: str) -> str:
        """
        Process a user query and return the response
        """
        result = self.chain({"question": query})
        return result["answer"]
