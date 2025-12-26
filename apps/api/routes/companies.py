from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from apps.api.core.db import get_db
from apps.api.schemas.company_schema import CompanyCreate, CompanyResponse
from apps.api.services.company_service import create_company, list_companies, get_company

router = APIRouter()


@router.post("/", response_model=CompanyResponse)
def create_company_route(payload: CompanyCreate, db: Session = Depends(get_db)):
    return create_company(db, payload)


@router.get("/", response_model=list[CompanyResponse])
def list_companies_route(db: Session = Depends(get_db)):
    return list_companies(db)


@router.get("/{company_id}", response_model=CompanyResponse)
def get_company_route(company_id: int, db: Session = Depends(get_db)):
    company = get_company(db, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return company