from typing import Annotated

from fastapi import APIRouter, File, Form, Query, Response, UploadFile
from sqlalchemy import delete, func, select

from app.api.deps import (
    CurrentUser,
    DbSession,
    get_dataset_or_404,
    parse_rule_specs,
    read_upload,
)
from app.core.exceptions import ConfigurationError, NotFoundError
from app.models import Dataset, DatasetProfile, DatasetRecord
from app.processing.loading import parse_key_columns, validate_key_columns
from app.schemas.common import Page
from app.schemas.dataset import DatasetKeyUpdate, DatasetOut, ProfileOut, RecordOut
from app.schemas.run import RunDetail, run_to_detail
from app.services.pipeline import create_dataset_from_upload

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.post("/upload", response_model=RunDetail, status_code=201)
def upload_dataset(
    file: Annotated[UploadFile, File()],
    name: Annotated[str, Form(min_length=1, max_length=200)],
    db: DbSession,
    user: CurrentUser,
    description: Annotated[str | None, Form(max_length=2000)] = None,
    rules: Annotated[str | None, Form()] = None,
    key_columns: Annotated[str | None, Form()] = None,
):
    """Upload a CSV, profile it, and run the first validation.

    'rules' is an optional JSON list of rule objects.
    'key_columns' is optional, comma-separated. If given, the valid rows are loaded
    into the database, identified by those columns. If not, no row is ever stored.
    """
    clean_name = name.strip()
    if not clean_name:
        raise ConfigurationError("Dataset name cannot be blank.")
    keys = parse_key_columns(key_columns)
    content, filename = read_upload(file)
    rule_specs = parse_rule_specs(rules)
    run = create_dataset_from_upload(
        db, user.id, content, filename, clean_name,
        description=description, rules=rule_specs, key_columns=keys,
    )
    return run_to_detail(run)


@router.get("", response_model=Page[DatasetOut])
def list_datasets(
    db: DbSession,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    mine = Dataset.user_id == user.id
    total = db.scalar(select(func.count()).select_from(Dataset).where(mine)) or 0
    rows = db.scalars(
        select(Dataset).where(mine).order_by(Dataset.id.desc()).limit(limit).offset(offset)
    ).all()
    return Page[DatasetOut](
        items=[DatasetOut.model_validate(r) for r in rows],
        total=total, limit=limit, offset=offset,
    )


@router.get("/{dataset_id}", response_model=DatasetOut)
def get_dataset(dataset_id: int, db: DbSession, user: CurrentUser):
    return DatasetOut.model_validate(get_dataset_or_404(db, dataset_id, user))


@router.patch("/{dataset_id}", response_model=DatasetOut)
def set_key_columns(dataset_id: int, body: DatasetKeyUpdate, db: DbSession, user: CurrentUser):
    """Turn loading on (a list of key columns) or off (null) for later runs.

    Turning it off keeps the records already loaded; DELETE .../records removes them.
    """
    dataset = get_dataset_or_404(db, dataset_id, user)
    dataset.key_columns = validate_key_columns(body.key_columns)
    db.commit()
    db.refresh(dataset)
    return DatasetOut.model_validate(dataset)


@router.get("/{dataset_id}/profile", response_model=ProfileOut)
def get_profile(dataset_id: int, db: DbSession, user: CurrentUser):
    get_dataset_or_404(db, dataset_id, user)
    profile = db.scalars(
        select(DatasetProfile)
        .where(DatasetProfile.dataset_id == dataset_id)
        .order_by(DatasetProfile.id.desc())
        .limit(1)
    ).first()
    if profile is None:
        raise NotFoundError("No profile found for this dataset.", {"dataset_id": dataset_id})
    return ProfileOut.model_validate(profile)


@router.get("/{dataset_id}/records", response_model=Page[RecordOut])
def list_records(
    dataset_id: int,
    db: DbSession,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """The rows loaded for this dataset (empty unless the dataset has key columns)."""
    get_dataset_or_404(db, dataset_id, user)
    mine = DatasetRecord.dataset_id == dataset_id
    total = db.scalar(select(func.count()).select_from(DatasetRecord).where(mine)) or 0
    rows = db.scalars(
        select(DatasetRecord).where(mine).order_by(DatasetRecord.id).limit(limit).offset(offset)
    ).all()
    return Page[RecordOut](
        items=[RecordOut.model_validate(r) for r in rows], total=total, limit=limit, offset=offset
    )


@router.delete("/{dataset_id}/records", status_code=204)
def delete_records(dataset_id: int, db: DbSession, user: CurrentUser):
    """Remove every loaded row of this dataset. The dataset and its history stay."""
    get_dataset_or_404(db, dataset_id, user)
    db.execute(delete(DatasetRecord).where(DatasetRecord.dataset_id == dataset_id))
    db.commit()
    return Response(status_code=204)
