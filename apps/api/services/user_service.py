from sqlalchemy.orm import Session
from apps.api.models.user_model import User
from apps.api.schemas.user_schema import UserCreate


def create_user(db: Session, payload: UserCreate):
    user = User(
        email=payload.email,
        clerk_id=payload.clerk_id,
        company_id=payload.company_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def assign_user_company(db: Session, user_id: str, company_id: int):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None

    user.company_id = company_id
    db.commit()
    db.refresh(user)
    return user