from sqlalchemy.orm import Session
from apps.api.models.company_model import Company
from apps.api.schemas.company_schema import CompanyCreate


def create_company(db: Session, payload: CompanyCreate):
    company = Company(name=payload.name)
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def list_companies(db: Session):
    return db.query(Company).all()


def get_company(db: Session, company_id: int):
    return db.query(Company).filter(Company.id == company_id).first()