import sys
import os
import asyncio
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from datetime import datetime
import uuid

from app.database.database import TranscriptionSessionLocal
from app.database.models import APIKey
from app.authentication.authen import generate_api_key

async def create_api_key(owner_name, owner_email, description=None):
    """Create a new API key for a user."""
    # Generate new API key
    api_key = generate_api_key()
    key_id = str(uuid.uuid4())
    
    # Create DB record
    db = TranscriptionSessionLocal()
    try:
        new_key = APIKey(
            key_id=key_id,
            key=api_key,
            owner_name=owner_name,
            owner_email=owner_email,
            description=description,
            is_active=True,
            created_at=datetime.utcnow()
        )
        
        db.add(new_key)
        db.commit()
        db.refresh(new_key)
        
        print(f"API Key created successfully!")
        print(f"Key ID: {key_id}")
        print(f"API Key: {api_key}")
        print(f"Owner: {owner_name}")
        print("\nIMPORTANT: Store this API key securely. It will not be shown again.")
        
    except Exception as e:
        db.rollback()
        print(f"Error creating API key: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python create_api_key.py <owner_name> <owner_email> [description]")
        sys.exit(1)
    
    owner_name = sys.argv[1]
    owner_email = sys.argv[2]
    description = sys.argv[3] if len(sys.argv) > 3 else None
    
    asyncio.run(create_api_key(owner_name, owner_email, description))