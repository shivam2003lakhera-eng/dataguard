import json
from typing import Annotated, Any

from fastapi import Depends, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    AuthenticationError,
    ConfigurationError,
    FileTooLargeError,
    NotFoundError,
)
from app.db.session import get_db
from app.models import Dataset, QualityRule, QualityRun, User
from app.schemas.rule import RuleCreate
from app.services.auth import SESSION_COOKIE, user_for_token

DbSession = Annotated[Session, Depends(get_db)]
CHUNK_SIZE = 1024 * 1024


def read_upload(upload: UploadFile) -> tuple[bytes, str]:
    """Read an upload in chunks, stopping as soon as it passes the size limit."""
    limit_mb = get_settings().max_file_size_mb
    limit = limit_mb * 1024 * 1024
    chunks: list[bytes] = []
    total = 0
    while chunk := upload.file.read(CHUNK_SIZE):
        total += len(chunk)
        if total > limit:
            raise FileTooLargeError(
                "File exceeds the maximum allowed size.", {"limit_mb": limit_mb}
            )
        chunks.append(chunk)
    return b"".join(chunks), upload.filename or ""


def parse_rule_specs(raw: str | None) -> list[dict[str, Any]]:
    """Turn the optional 'rules' form field (a JSON string) into rule dicts."""
    if not raw or not raw.strip():
        return []
    try:
        items = json.loads(raw)
        if not isinstance(items, list):
            raise ValueError("not a list")
        return [RuleCreate.model_validate(i).model_dump(exclude={"enabled"}) for i in items]
    except ValueError:  # JSON errors and pydantic validation errors both subclass ValueError
        raise ConfigurationError(
            "'rules' must be a JSON list of rule objects "
            "(name, rule_type, configuration, severity)."
        ) from None


def get_current_user(request: Request, db: DbSession) -> User:
    user = user_for_token(db, request.cookies.get(SESSION_COOKIE))
    if user is None:
        raise AuthenticationError("You are not logged in.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_dataset_or_404(db: Session, dataset_id: int, user: User) -> Dataset:
    """Only the owner can reach a dataset. Anyone else gets the same 404 as a missing id."""
    dataset = db.scalar(
        select(Dataset).where(Dataset.id == dataset_id, Dataset.user_id == user.id)
    )
    if dataset is None:
        raise NotFoundError("Dataset not found.", {"dataset_id": dataset_id})
    return dataset


def get_rule_or_404(db: Session, rule_id: int, user: User) -> QualityRule:
    rule = db.scalar(
        select(QualityRule)
        .join(Dataset, Dataset.id == QualityRule.dataset_id)
        .where(QualityRule.id == rule_id, Dataset.user_id == user.id)
    )
    if rule is None:
        raise NotFoundError("Rule not found.", {"rule_id": rule_id})
    return rule


def get_run_or_404(db: Session, run_id: int, user: User) -> QualityRun:
    run = db.scalar(
        select(QualityRun)
        .join(Dataset, Dataset.id == QualityRun.dataset_id)
        .where(QualityRun.id == run_id, Dataset.user_id == user.id)
    )
    if run is None:
        raise NotFoundError("Run not found.", {"run_id": run_id})
    return run