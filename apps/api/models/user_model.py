import uuid
from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.orm import relationship
from apps.api.core.db import Base

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    clerk_id = Column(String, unique=True, nullable=True)  # soft auth for now
    email = Column(String, unique=True, nullable=True)

    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)

    # Relationships
    company = relationship("Company", back_populates="users")