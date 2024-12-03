from fastapi import (
    FastAPI,
    UploadFile,
    File,
    HTTPException,
    Depends,
    status,
    BackgroundTasks,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, constr
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from typing import Optional
from sqlalchemy.orm import Session
import shutil
import os
import secrets
import time
from .chatbot import DocumentChatbot
from .database import get_db, DBUser
import uuid

# Security Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-keep-it-secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES = 15
MAX_LOGIN_ATTEMPTS = 5
LOGIN_COOLDOWN_MINUTES = 15

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize chatbot
chatbot = None


# User Models
class UserBase(BaseModel):
    username: constr(min_length=3, max_length=50)
    email: EmailStr


class UserCreate(UserBase):
    password: constr(min_length=8)


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None


class User(UserBase):
    disabled: bool = False

    class Config:
        orm_mode = True


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None


class ChatMessage(BaseModel):
    message: str


class PasswordReset(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: constr(min_length=8)


# Document Models
class Document(BaseModel):
    id: str
    filename: str
    uploaded_at: datetime
    user_id: str


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def get_user(db: Session, username: str):
    return db.query(DBUser).filter(DBUser.username == username).first()


def get_user_by_email(db: Session, email: str):
    return db.query(DBUser).filter(DBUser.email == email).first()


def authenticate_user(db: Session, username: str, password: str):
    user = get_user(db, username)
    if not user:
        return False

    # Check for account lockout
    if user.failed_login_attempts >= MAX_LOGIN_ATTEMPTS:
        if user.last_failed_login:
            lockout_time = datetime.fromtimestamp(user.last_failed_login) + timedelta(
                minutes=LOGIN_COOLDOWN_MINUTES
            )
            if datetime.now() < lockout_time:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Account locked. Try again after {lockout_time}",
                )
            # Reset counter after cooldown
            user.failed_login_attempts = 0
            db.commit()

    if not verify_password(password, user.hashed_password):
        # Increment failed login attempts
        user.failed_login_attempts += 1
        user.last_failed_login = datetime.now().timestamp()
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password"
        )

    # Reset failed login attempts on successful login
    user.failed_login_attempts = 0
    user.last_failed_login = None
    db.commit()
    return user


def create_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception

    user = get_user(db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: DBUser = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def initialize_chatbot():
    global chatbot
    try:
        if chatbot is None:
            print("Initializing chatbot...")
            chatbot = DocumentChatbot()
            
            # Check if documents directory exists
            if not os.path.exists("documents"):
                os.makedirs("documents")
                print("Created documents directory")
                return None
            
            # Check if there are any documents
            documents = os.listdir("documents")
            if not documents:
                print("No documents found in documents directory")
                return None
            
            print(f"Found {len(documents)} documents")
            chatbot.setup_chain()
            print("Chatbot initialized successfully")
            return chatbot
    except Exception as e:
        print(f"Error initializing chatbot: {str(e)}")
        if "Please upload some documents first" in str(e):
            return None
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize chatbot: {str(e)}",
        )


# Initialize on startup
initialize_chatbot()


# Authentication endpoints
@app.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_token_expires = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    access_token = create_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    refresh_token = create_token(
        data={"sub": user.username, "refresh": True},
        expires_delta=refresh_token_expires,
    )

    # Store refresh token
    user.refresh_token = refresh_token
    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@app.post("/register", response_model=User)
async def register_user(user: UserCreate, db: Session = Depends(get_db)):
    print(f"Received registration request for user: {user.username}")

    # Check if username exists
    db_user = get_user(db, username=user.username)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    # Check if email exists
    db_user = get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    # Add basic password validation
    if len(user.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters",
        )
    if not any(c.isupper() for c in user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one uppercase letter",
        )
    if not any(c.isdigit() for c in user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one number",
        )

    # Create new user
    hashed_password = get_password_hash(user.password)
    db_user = DBUser(
        username=user.username, email=user.email, hashed_password=hashed_password
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    print(f"Successfully registered user: {user.username}")
    return db_user


@app.post("/refresh-token", response_model=Token)
async def refresh_access_token(refresh_token: str, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        user = get_user(db, username)
        if not user or user.refresh_token != refresh_token:
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        # Create new tokens
        access_token = create_token(
            data={"sub": username},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        new_refresh_token = create_token(
            data={"sub": username, "refresh": True},
            expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        )

        # Update stored refresh token
        user.refresh_token = new_refresh_token
        db.commit()

        return {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
        }
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


@app.post("/reset-password")
async def request_password_reset(
    reset_request: PasswordReset, db: Session = Depends(get_db)
):
    # Find user by email
    user = get_user_by_email(db, reset_request.email)
    if not user:
        # Return success even if email not found to prevent email enumeration
        return {"message": "If the email exists, a password reset link will be sent"}

    # Generate reset token
    reset_token = secrets.token_urlsafe(32)
    user.reset_token = reset_token
    user.reset_token_expires = (
        datetime.now() + timedelta(minutes=PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)
    ).timestamp()
    db.commit()

    # In production, send email with reset token
    print(f"Password reset token for {user.username}: {reset_token}")

    return {"message": "If the email exists, a password reset link will be sent"}


@app.post("/reset-password-confirm")
async def confirm_password_reset(
    reset_confirm: PasswordResetConfirm, db: Session = Depends(get_db)
):
    # Find user by reset token
    user = db.query(DBUser).filter(DBUser.reset_token == reset_confirm.token).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    if (
        not user.reset_token_expires
        or datetime.now().timestamp() > user.reset_token_expires
    ):
        raise HTTPException(status_code=400, detail="Reset token has expired")

    # Update password
    user.hashed_password = get_password_hash(reset_confirm.new_password)
    user.reset_token = None
    user.reset_token_expires = None
    db.commit()

    return {"message": "Password has been reset successfully"}


@app.put("/users/me", response_model=User)
async def update_user(
    user_update: UserUpdate,
    current_user: DBUser = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if user_update.email:
        # Check if email is already used
        existing_user = get_user_by_email(db, user_update.email)
        if existing_user and existing_user.username != current_user.username:
            raise HTTPException(status_code=400, detail="Email already registered")
        current_user.email = user_update.email

    if user_update.current_password and user_update.new_password:
        if not verify_password(
            user_update.current_password, current_user.hashed_password
        ):
            raise HTTPException(status_code=400, detail="Incorrect current password")
        current_user.hashed_password = get_password_hash(user_update.new_password)

    db.commit()
    db.refresh(current_user)
    return current_user


@app.get("/users/me", response_model=User)
async def read_users_me(current_user: DBUser = Depends(get_current_active_user)):
    return current_user


# Chat endpoints
@app.post("/upload")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: DBUser = Depends(get_current_active_user),
):
    global chatbot
    print(f"Received upload request for file: {file.filename}")
    try:
        # Create documents directory if it doesn't exist
        os.makedirs("documents", exist_ok=True)

        # Check file size (limit to 50MB)
        file_size = 0
        content = bytearray()

        # Read file in chunks to check size
        chunk_size = 1024 * 1024  # 1MB chunks
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            file_size += len(chunk)
            content.extend(chunk)

            # Check if file is too large (50MB limit)
            if file_size > 50 * 1024 * 1024:  # 50MB
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="File too large. Maximum size is 50MB.",
                )

        # Save the uploaded file
        file_path = os.path.join("documents", file.filename)
        with open(file_path, "wb") as buffer:
            buffer.write(content)

        # Initialize new chatbot instance in the background
        def init_chatbot():
            global chatbot
            try:
                chatbot = DocumentChatbot()
                chatbot.setup_chain()
                print(f"Successfully processed file: {file.filename}")
            except Exception as e:
                print(f"Error processing document: {str(e)}")
                # Delete the file if processing fails
                try:
                    os.remove(file_path)
                except:
                    pass
                raise e

        background_tasks.add_task(init_chatbot)

        return {
            "message": f"Document uploaded successfully: {file.filename}. Processing in background..."
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error in upload endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@app.post("/chat")
async def chat(
    message: ChatMessage, current_user: DBUser = Depends(get_current_active_user)
):
    global chatbot
    print(f"Received chat request with message: {message.message}")
    try:
        # Check if documents exist
        if not os.path.exists("documents") or not os.listdir("documents"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please upload some documents first",
            )

        if chatbot is None:
            print("Chatbot not initialized, attempting to initialize...")
            chatbot = initialize_chatbot()

        if not hasattr(chatbot, "chain"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please upload some documents first",
            )

        print("Processing message with chatbot...")
        response = chatbot.chat(message.message)
        print(f"Got response from chatbot: {response}")

        return {"response": response}
    except HTTPException as he:
        raise he
    except Exception as e:
        error_msg = str(e)
        print(f"Error in chat endpoint: {error_msg}")
        if "Please upload some documents first" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please upload some documents first",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# Health check endpoint
@app.get("/health")
async def health_check():
    try:
        # Check if chatbot is initialized and has documents
        has_documents = os.path.exists("documents") and bool(os.listdir("documents"))
        if chatbot is None and has_documents:
            initialize_chatbot()
        return {
            "status": "healthy",
            "chatbot_initialized": chatbot is not None,
            "has_documents": has_documents,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@app.get("/documents", response_model=list[Document])
async def list_documents(current_user: DBUser = Depends(get_current_active_user)):
    try:
        documents_dir = "documents"
        if not os.path.exists(documents_dir):
            return []

        documents = []
        for filename in os.listdir(documents_dir):
            file_path = os.path.join(documents_dir, filename)
            if os.path.isfile(file_path):
                doc_id = str(uuid.uuid4())
                doc = Document(
                    id=doc_id,
                    filename=filename,
                    uploaded_at=datetime.fromtimestamp(os.path.getctime(file_path)),
                    user_id=current_user.username,
                )
                documents.append(doc)

        return sorted(documents, key=lambda x: x.uploaded_at, reverse=True)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@app.delete("/documents/{document_id}")
async def delete_document(
    document_id: str, current_user: DBUser = Depends(get_current_active_user)
):
    try:
        documents_dir = "documents"
        deleted = False

        for filename in os.listdir(documents_dir):
            file_path = os.path.join(documents_dir, filename)
            if os.path.isfile(file_path):
                try:
                    os.remove(file_path)
                    deleted = True
                    break
                except Exception as e:
                    print(f"Error deleting file {filename}: {str(e)}")

        if deleted:
            # Reinitialize chatbot after document deletion
            global chatbot
            chatbot = None
            if os.listdir(documents_dir):  # If there are still documents
                initialize_chatbot()

            return {"message": "Document deleted successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
