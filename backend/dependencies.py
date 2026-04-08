from fastapi import Header, HTTPException, Depends
from backend.config import settings

async def verify_auth_token(authorization: str = Header(None)):
    if settings.AUTH_TOKEN:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Unauthorized")
        token = authorization.split(" ")[1]
        if token != settings.AUTH_TOKEN:
            raise HTTPException(status_code=401, detail="Unauthorized")
