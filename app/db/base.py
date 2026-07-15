"""Declarative base for all SQLAlchemy ORM models."""
from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all ORM models. Alembic's env.py targets Base.metadata."""
    pass
