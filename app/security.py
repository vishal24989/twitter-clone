from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2
from fastapi.openapi.models import OAuthFlows as OAuthFlowsModel
from sqlalchemy.orm import Session
import os
from dotenv import load_dotenv

from . import models, schemas, database

load_dotenv()

# --- Configuration from .env ---
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

# --- Custom Security Class to Read from Cookie ---
class OAuth2PasswordBearerWithCookie(OAuth2):
    def __init__(
        self,
        tokenUrl: str,
        scheme_name: Optional[str] = None,
        scopes: Optional[dict] = None,
        auto_error: bool = True,
    ):
        if not scopes:
            scopes = {}
        flows = OAuthFlowsModel(password={"tokenUrl": tokenUrl, "scopes": scopes})
        super().__init__(flows=flows, scheme_name=scheme_name, auto_error=auto_error)

    async def __call__(self, request: Request) -> Optional[str]:
        token = request.cookies.get("access_token")

        if not token:
            if self.auto_error:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Not authenticated",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            else:
                return None
        
        parts = token.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            if self.auto_error:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token format",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            else:
                return None
        
        return parts[1]

oauth2_scheme = OAuth2PasswordBearerWithCookie(tokenUrl="login")

# --- Password Hashing ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

# --- JWT Token Creation ---
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# --- User Retrieval Dependency (Strict) ---
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(database.get_db)):
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
        token_data = schemas.TokenData(username=username)
    except JWTError:
        raise credentials_exception
    
    user = db.query(models.User).filter(models.User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    return user

# --- User Retrieval Dependency (Optional) with DEBUGGING ---
async def try_get_current_user(request: Request, db: Session = Depends(database.get_db)) -> Optional[models.User]:
    print("\n--- [DEBUG] Attempting to get current user from cookie ---")
    try:
        token = request.cookies.get("access_token")
        if not token:
            print("[DEBUG] No access_token cookie found. Returning None.")
            return None

        print(f"[DEBUG] Found token in cookie: {token[:30]}...")

        parts = token.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            print("[DEBUG] Invalid token format. Returning None.")
            return None
        
        clean_token = parts[1]
        
        payload = jwt.decode(clean_token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        print(f"[DEBUG] Decoded username from token: '{username}'")
        
        if username is None:
            print("[DEBUG] Username is None in payload. Returning None.")
            return None
        
        user = db.query(models.User).filter(models.User.username == username).first()
        
        if user:
            print(f"[DEBUG] Success! Found user '{user.username}' in DB.")
        else:
            print(f"[DEBUG] User '{username}' was not found in the database. Returning None.")
        
        return user
    
    except Exception as e:
        print(f"[DEBUG] An unexpected exception occurred: {e}")
        return None