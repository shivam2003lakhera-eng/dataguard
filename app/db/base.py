from enum import StrEnum

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Parent class of all database models."""


def in_values(column: str, enum_class: type[StrEnum]) -> str:
    """SQL text for a CHECK that a column only holds an enum's values."""
    values = ", ".join(f"'{member.value}'" for member in enum_class)
    return f"{column} IN ({values})"