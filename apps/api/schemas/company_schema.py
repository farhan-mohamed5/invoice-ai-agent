from pydantic import BaseModel
from typing import Optional


class CompanyCreate(BaseModel):
    name: str


class CompanyResponse(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True