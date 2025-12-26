from fastapi import APIRouter, Depends
from apps.api.core.security import get_current_user

router = APIRouter()

@router.get("/me")
async def get_me(user = Depends(get_current_user)):
    return {"user": user}