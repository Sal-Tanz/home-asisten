# backend/app/auth.py
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from passlib.hash import bcrypt
from starlette.middleware.sessions import SessionMiddleware
from app.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])

settings = get_settings()


class LoginRequest(BaseModel):
    password: str


def verify_password(plain_password: str) -> bool:
    """Verify password against stored hash"""
    return bcrypt.verify(plain_password, settings.app_password_hash)


def get_current_user(request: Request) -> bool:
    """Dependency to check if user is authenticated"""
    session = request.session
    if not session.get("authenticated"):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return True


@router.post("/login")
async def login(request: LoginRequest, req: Request):
    """Login with password"""
    if not verify_password(request.password):
        raise HTTPException(status_code=401, detail="Invalid password")

    # Set session
    req.session["authenticated"] = True

    return {"success": True, "message": "Login successful"}


@router.post("/logout")
async def logout(req: Request, _: bool = Depends(get_current_user)):
    """Logout and clear session"""
    req.session.clear()
    return {"success": True, "message": "Logout successful"}


@router.get("/status")
async def auth_status(req: Request):
    """Check authentication status"""
    authenticated = req.session.get("authenticated", False)
    return {"authenticated": authenticated}
