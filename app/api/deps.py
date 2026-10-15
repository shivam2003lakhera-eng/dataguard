import json
from typing import Annotated, Any

from fastapi import Depends, UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ConfigurationError, FileTooLargeError, NotFoundError
from app.db.session import get_db
from app.models import Dataset, QualityRule
from app.schemas.rule import RuleCreate

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


def get_dataset_or_404(db: Session, dataset_id: int) -> Dataset:
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise NotFoundError("Dataset not found.", {"dataset_id": dataset_id})
    return dataset


def get_rule_or_404(db: Session, rule_id: int) -> QualityRule:
    rule = db.get(QualityRule, rule_id)
    if rule is None:
        raise NotFoundError("Rule not found.", {"rule_id": rule_id})
    return rule