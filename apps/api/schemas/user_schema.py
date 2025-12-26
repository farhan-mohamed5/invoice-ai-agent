from pydantic import BaseModel
from typing import Optional


class UserCreate(BaseModel):
    email: Optional[str]
    clerk_id: Optional[str]
    company_id: Optional[int]  # nullable until user assigns a company


class UserResponse(BaseModel):
    id: str
    email: Optional[str]
    clerk_id: Optional[str]
    company_id: Optional[int]

    class Config:
        from_attributes = True