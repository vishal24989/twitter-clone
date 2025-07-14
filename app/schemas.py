from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# --- User Schemas ---

class UserBase(BaseModel):
    email: str
    username: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int

    class Config:
        # Allows Pydantic to work with ORM models
        orm_mode = True

# --- Tweet Schemas ---

class TweetBase(BaseModel):
    text: str

class TweetCreate(TweetBase):
    pass

class Tweet(TweetBase):
    id: int
    author_id: int
    created_at: datetime
    # Nested User schema to include author details in the response
    author: User

    class Config:
        orm_mode = True

# --- Token Schemas ---

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None