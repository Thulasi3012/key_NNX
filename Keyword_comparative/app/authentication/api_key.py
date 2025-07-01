from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List
import uuid

from app.database.database import get_db
from app.database.models import APIKey
from app.authentication.authen import generate_api_key, get_api_key
from app.authentication.config import settings
from pydantic import BaseModel
from datetime import datetime

# Pydantic models for API responses
class APIKeyCreate(BaseModel):
    owner_name: str
    owner_email: str
    description: str = None

class APIKeyInfo(BaseModel):
    key_id: str
    owner_name: str
    owner_email: str
    description: str = None
    is_active: bool
    created_at: datetime
    last_used: datetime = None

class APIKeyResponse(BaseModel):
    key_id: str
    api_key: str
    owner_name: str

# Create router
app = APIRouter()

@app.post("/keys", response_model=APIKeyResponse)
async def create_api_key(
    key_data: APIKeyCreate,
    db: Session = Depends(get_db),
    _: str = Depends(get_api_key)  # Only admins can create keys (currently any authenticated user)
):
    """Create a new API key."""
    
    # Generate new API key
    api_key = generate_api_key()
    key_id = str(uuid.uuid4())
    
    # Create DB record
    new_key = APIKey(
        key_id=key_id,
        key=api_key,
        owner_name=key_data.owner_name,
        owner_email=key_data.owner_email,
        description=key_data.description,
        is_active=True,
        created_at=datetime.utcnow()
    )
    
    db.add(new_key)
    db.commit()
    db.refresh(new_key)
    
    # Return the key (this is the only time the full key will be shown)
    return {
        "key_id": key_id,
        "api_key": api_key,
        "owner_name": key_data.owner_name
    }

@app.get("/keys", response_model=List[APIKeyInfo])
async def list_api_keys(
    db: Session = Depends(get_db),
    _: str = Depends(get_api_key)  # Only authenticated users can list keys
):
    """List all API keys (without showing the actual keys)."""
    keys = db.query(APIKey).all()
    return keys

@app.put("/keys/{key_id}/deactivate")
async def deactivate_api_key(
    key_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(get_api_key)  # Only authenticated users can deactivate keys
):
    """Deactivate an API key."""
    key = db.query(APIKey).filter(APIKey.key_id == key_id).first()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    key.is_active = False
    db.commit()
    
    return {"message": f"API key {key_id} deactivated successfully"}

@app.put("/keys/{key_id}/activate")
async def activate_api_key(
    key_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(get_api_key)  # Only authenticated users can activate keys
):
    """Activate an API key."""
    key = db.query(APIKey).filter(APIKey.key_id == key_id).first()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    key.is_active = True
    db.commit()
    
    return {"message": f"API key {key_id} activated successfully"}