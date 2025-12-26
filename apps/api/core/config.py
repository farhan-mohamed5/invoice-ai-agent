import os
from pydantic import BaseSettings

class Settings(BaseSettings):
    # Absolute SQLite path 
    DATABASE_URL: str = "sqlite:////Users/farhanmohamed/CS_Projects/invoice_agent/invoice_agent_data/invoices.db"

    # Redis 
    REDIS_URL: str = "redis://localhost:6379/0"

    # Soft Clerk auth 
    CLERK_JWKS_URL: str = "https://api.clerk.com/.well-known/jwks.json"

    class Config:
        env_file = ".env"

settings = Settings()