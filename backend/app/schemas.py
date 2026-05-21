"""Pydantic schemas for request/response validation"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime


# User Schemas
class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)


class UserRegister(UserBase):
    password: str = Field(..., min_length=8)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(UserBase):
    id: int
    created_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # Seconds until expiration


class TokenRefresh(BaseModel):
    refresh_token: str


# Chat Schemas
class MessageCreate(BaseModel):
    query: str = Field(..., min_length=1)
    regenerate: bool = False


class MessageResponse(BaseModel):
    role: str
    message: str
    created_at: datetime

    class Config:
        from_attributes = True


class ChatResponse(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChatDetailResponse(ChatResponse):
    messages: List[MessageResponse]


# Document Schemas
class DocumentResponse(BaseModel):
    id: int
    filename: str
    original_filename: str
    file_size: int
    chunk_count: int
    uploaded_at: datetime

    class Config:
        from_attributes = True


class UploadResponse(BaseModel):
    message: str
    filename: str
    original_filename: str
    chunks: int
    upload_id: int


class RAGResponse(BaseModel):
    answer: str
    sources: List[dict]
    query: str


class ErrorResponse(BaseModel):
    error: str
    code: str
    request_id: Optional[str] = None
