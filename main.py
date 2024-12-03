import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from src.chatbot import DocumentChatbot

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI()

# Add CORS middleware with more permissive settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # More permissive for testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize chatbot
chatbot = None


def initialize_chatbot():
    global chatbot
    try:
        if chatbot is None:
            print("Initializing chatbot...")
            chatbot = DocumentChatbot()
            chatbot.setup_vectorstore()
            chatbot.setup_chain()
            print("Chatbot initialized successfully")
    except Exception as e:
        print(f"Error initializing chatbot: {str(e)}")


# Initialize on startup
initialize_chatbot()


class ChatMessage(BaseModel):
    message: str


@app.post("/chat")
async def chat(message: ChatMessage):
    print(f"Received chat request with message: {message.message}")
    global chatbot
    try:
        if chatbot is None:
            print("Chatbot not initialized, attempting to initialize...")
            initialize_chatbot()
            if chatbot is None:
                raise HTTPException(
                    status_code=500, detail="Failed to initialize chatbot"
                )

        print("Processing message with chatbot...")
        response = chatbot.chat(message.message)
        print(f"Got response from chatbot: {response}")

        return {"response": response}
    except Exception as e:
        error_msg = str(e)
        print(f"Error in chat endpoint: {error_msg}")
        if "Please upload some documents first" in error_msg:
            print("Attempting to reinitialize chatbot...")
            initialize_chatbot()
            try:
                response = chatbot.chat(message.message)
                return {"response": response}
            except Exception as e:
                print(f"Error after reinitialization: {str(e)}")
        raise HTTPException(status_code=500, detail=error_msg)


@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    print(f"Received upload request for file: {file.filename}")
    global chatbot
    try:
        # Create documents directory if it doesn't exist
        os.makedirs("documents", exist_ok=True)

        # Save the uploaded file
        file_path = os.path.join("documents", file.filename)
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        if chatbot is None:
            initialize_chatbot()

        # Process the document
        success = chatbot.upload_document(file_path)
        if success:
            print(f"Successfully uploaded and processed file: {file.filename}")
            return {"message": f"Document uploaded successfully: {file.filename}"}
        else:
            print(f"Failed to process document: {file.filename}")
            raise HTTPException(status_code=400, detail="Failed to process document")
    except Exception as e:
        print(f"Error in upload endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    print("Starting server...")
    uvicorn.run(app, host="0.0.0.0", port=5000, log_level="info")
