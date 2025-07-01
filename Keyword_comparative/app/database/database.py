import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from urllib.parse import quote_plus

load_dotenv()

# Azure PostgreSQL DB (Transcription DB)
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = quote_plus(os.getenv("DB_PASSWORD"))
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

TRANSCRIPTION_DB_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
transcription_engine = create_engine(TRANSCRIPTION_DB_URL)
TranscriptionSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=transcription_engine)

def get_db():
    """Get a database session."""
    db = TranscriptionSessionLocal()
    try:
        yield db
    finally:
        db.close()

