from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class DatasetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    original_filename: str
    row_count: int
    column_count: int
    created_at: datetime
    key_columns: list[str] | None = None


class DatasetKeyUpdate(BaseModel):
    """null turns loading off. Records that were already loaded are kept."""

    model_config = ConfigDict(extra="forbid")

    key_columns: list[str] | None


class RecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    row_key: str
    data: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dataset_id: int
    profile_data: dict[str, Any]
    created_at: datetime
