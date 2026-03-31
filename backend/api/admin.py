from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.db.user_repository import UserRepository
from backend.services.auth import get_current_user, hash_password

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Auth dependency — admin only
# ---------------------------------------------------------------------------

async def require_admin(user=Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreateAgentRequest(BaseModel):
    email: str
    password: str
    name: str
    role: str = "agent"  # agent or admin
    team: Optional[str] = "general"


class UpdateAgentRequest(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    team: Optional[str] = None
    password: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/users")
async def list_users(role: Optional[str] = None, team: Optional[str] = None, _=Depends(require_admin)):
    """List all users (agents, admins, customers)."""
    users = await UserRepository.find_all(role=role, team=team)
    return {"users": users, "count": len(users)}


@router.post("/users")
async def create_agent(request: CreateAgentRequest, _=Depends(require_admin)):
    """Create a new agent or admin account."""
    if request.role not in ("agent", "admin"):
        raise HTTPException(status_code=400, detail="Role must be 'agent' or 'admin'")
    if len(request.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    existing = await UserRepository.find_by_email(request.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    user_id = await UserRepository.create(
        email=request.email,
        password_hash=hash_password(request.password),
        name=request.name,
        role=request.role,
        team=request.team,
    )
    return {"ok": True, "user_id": user_id}


@router.patch("/users/{user_id}")
async def update_user(user_id: str, request: UpdateAgentRequest, _=Depends(require_admin)):
    """Update an agent/admin's details."""
    updates = {}
    if request.name is not None:
        updates["name"] = request.name
    if request.role is not None:
        if request.role not in ("agent", "admin", "customer"):
            raise HTTPException(status_code=400, detail="Invalid role")
        updates["role"] = request.role
    if request.team is not None:
        updates["team"] = request.team
    if request.password is not None:
        if len(request.password) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
        updates["password_hash"] = hash_password(request.password)

    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    updated = await UserRepository.update(user_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True, "user_id": user_id}


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, admin=Depends(require_admin)):
    """Delete a user account."""
    # Prevent admin from deleting themselves
    if admin.get("sub") == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    deleted = await UserRepository.delete(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True, "user_id": user_id}
