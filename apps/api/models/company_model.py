from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from apps.api.core.db import Base

class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)

    # Relationship: one-to-many (companies → invoices)
    invoices = relationship("Invoice", back_populates="company")