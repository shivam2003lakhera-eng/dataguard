from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RuleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200)
    rule_type: str = Field(min_length=1, max_length=50)
    configuration: dict[str, Any] = Field(default_factory=dict)
    severity: str = "MEDIUM"
    enabled: bool = True


class RuleUpdate(BaseModel):
    """Only these fields can change. rule_type is deliberately absent."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=200)
    configuration: dict[str, Any] | None = None
    severity: str | None = None
    enabled: bool | None = None


class RuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dataset_id: int
    name: str
    rule_type: str
    configuration: dict[str, Any]
    severity: str
    enabled: bool
    created_at: datetime