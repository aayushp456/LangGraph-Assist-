from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from backend.db.user_repository import UserRepository
from backend.services.auth import (
    create_token,
    get_current_user,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    token: str
    user: dict


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/register", response_model=AuthResponse)
async def register(request: RegisterRequest):
    """Register a new customer account."""
    if len(request.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    existing = await UserRepository.find_by_email(request.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    pw_hash = hash_password(request.password)
    user_id = await UserRepository.create(
        email=request.email,
        password_hash=pw_hash,
        name=request.name,
        role="customer",
    )

    token = create_token(user_id, request.email.lower().strip(), "customer")
    return AuthResponse(
        token=token,
        user={"user_id": user_id, "email": request.email.lower().strip(), "name": request.name, "role": "customer", "team": None},
    )


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest):
    """Login for customers, agents, and admins."""
    user = await UserRepository.find_by_email(request.email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_token(user["user_id"], user["email"], user["role"], user.get("team"))
    return AuthResponse(
        token=token,
        user={
            "user_id": user["user_id"],
            "email": user["email"],
            "name": user["name"],
            "role": user["role"],
            "team": user.get("team"),
        },
    )


@router.get("/me")
async def get_me(user=Depends(get_current_user)):
    """Validate token and return current user info."""
    from backend.db.user_repository import UserRepository

    db_user = await UserRepository.find_by_id(user["sub"])
    if not db_user:
        raise HTTPException(status_code=401, detail="User not found")

    return {
        "user_id": db_user["user_id"],
        "email": db_user["email"],
        "name": db_user["name"],
        "role": db_user["role"],
        "team": db_user.get("team"),
    }


# ---------------------------------------------------------------------------
# Seed default admin + agent (called on startup)
# ---------------------------------------------------------------------------

async def seed_default_users():
    """Create default admin and agent if they don't exist."""
    # Default admin
    if not await UserRepository.find_by_email("admin@support.local"):
        await UserRepository.create(
            email="admin@support.local",
            password_hash=hash_password("admin123"),
            name="Admin",
            role="admin",
            team=None,
        )
        print("Seeded default admin: admin@support.local / admin123")

    # Default general agent
    if not await UserRepository.find_by_email("agent@support.local"):
        await UserRepository.create(
            email="agent@support.local",
            password_hash=hash_password("agent123"),
            name="General Agent",
            role="agent",
            team="general",
        )
        print("Seeded default agent: agent@support.local / agent123")
