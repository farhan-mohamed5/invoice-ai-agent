from fastapi import Request

async def get_current_user(request: Request):
    """
    Soft-mode authentication:
    - Does NOT enforce Clerk
    - Returns a dummy user object for MVP
    - Replace later with real Clerk JWT validation
    """
    return {"id": "demo-user", "company_id": None}