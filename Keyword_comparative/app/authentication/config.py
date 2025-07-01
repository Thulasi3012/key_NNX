import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    
    PORT: int = int(os.getenv("PORT", "8000"))
    HOST: str = os.getenv("HOST", "0.0.0.0")
    
    # Database Configuration
    DB_HOST: str = os.getenv("DB_HOST", "40.81.235.116")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_NAME: str = os.getenv("DB_NAME", "advincidb")
    DB_USER: str = os.getenv("DB_USER", "advenadmin")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")

    MASTER_API_KEY: str = os.getenv("MASTER_API_KEY", "dev-master-key-never-use-in-production")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")  # "development", "testing", "production"
    AUTH_REQUIRED: bool = os.getenv("AUTH_REQUIRED", "True").lower() in ("true", "1", "t")
    
    # Configure Pydantic to ignore extra fields
    model_config = {
        "extra": "ignore",
        "env_file": ".env"
    }

# Create global settings instance
settings = Settings()