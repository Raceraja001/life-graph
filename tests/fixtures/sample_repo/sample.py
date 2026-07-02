"""Sample module for testing code analysis."""
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel


class UserCreate(BaseModel):
    """User creation schema."""
    name: str
    email: str


def get_user(user_id: int) -> Optional[dict]:
    """Get user by ID."""
    try:
        return {"id": user_id}
    except ValueError as e:
        raise RuntimeError(f"Invalid user: {e}") from e


async def create_user(data: UserCreate) -> dict:
    """Create a new user."""
    return {"name": data.name, "email": data.email}
