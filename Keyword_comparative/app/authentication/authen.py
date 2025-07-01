from fastapi import Depends, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
from starlette.status import HTTP_403_FORBIDDEN
import secrets
import logging
from sqlalchemy.orm import Session
from typing import Optional
from app.database.database import get_db
from app.authentication.config import settings 
from app.database.models import APIKey

# Configure logging
logger = logging.getLogger(__name__)

# Create API key header scheme
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# Function to generate new API keys
def generate_api_key() -> str:
    """Generate a secure random API key."""
    return secrets.token_urlsafe(32)

# Function to validate API key
async def get_api_key(
    api_key_header: str = Security(api_key_header),
    db: Session = Depends(get_db)
) -> str:
    """Validate API key from header."""
    if api_key_header is None:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN, 
            detail="API key missing"
        )

    # If we're in dev/test mode and using the master key, allow access
    if settings.ENVIRONMENT in ["development", "testing"] and api_key_header == settings.MASTER_API_KEY:
        logger.info("Access granted using master API key")
        return api_key_header
    
    # Check against database of valid API keys
    from app.database.models import APIKey
    
    api_key = db.query(APIKey).filter(
        APIKey.key == api_key_header,
        APIKey.is_active == True
    ).first()
    
    if not api_key:
        logger.warning(f"Invalid API key attempt: {api_key_header[:8]}...")
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN, 
            detail="Invalid or inactive API key"
        )
    
    # Update last used timestamp
    from datetime import datetime
    api_key.last_used = datetime.utcnow()
    db.commit()
    
    logger.info(f"Authenticated request with key ID: {api_key.key_id}")
    return api_key_header 

#to get an Owner name who are currenty using the API key

def get_api_owner(api_key: str, db: Session) -> str:
    """
    Get the owner name from the API key.
    """
    key_entry = db.query(APIKey).filter_by(key=api_key, is_active=True).first()
    if not key_entry:
        raise HTTPException(status_code=403, detail="Invalid or inactive API key.")
    return key_entry.owner_name
