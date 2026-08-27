import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./review_system.db"
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    FREE_MODEL: str = "google/gemma-2-9b-it:free"
    
    class Config:
        env_file = ".env"

settings = Settings()
