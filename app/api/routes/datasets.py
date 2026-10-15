from typing import Annotated

from fastapi import APIRouter, File, Form, Query, UploadFile
from sqlalchemy import func, select

from app.api.deps import DbSession, get_dataset_or_404, parse_rule_specs, read_upload
from app.core.exceptions import ConfigurationError, NotFoundError
from app.models import Dataset, DatasetProfile
from app.schemas.common import Page
from app.schemas.dataset import DatasetOut, ProfileOut
from app.schemas.run import RunDetail, run_to_detail
from app.services.pipeline import create_dataset_from_upload

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.post("/upload", response_model=RunDetail, status_code=201)
def upload_dataset(
    file: Annotated[UploadFile, File()],
    name: Annotated[str, Form(min_length=1, max_length=200)],
    db: DbSession,
    description: Annotated[str | None, Form(max_length=2000)] = None,
    rules: Annotated[str | None, Form()] = None,
):
    """Upload a CSV, profile it, and run the first validation.

    'rules' is an optional JSON list of rule objects.
    """
    clean_name = name.strip()
    if not clean_name:
        raise ConfigurationError("Dataset name cannot be blank.")
    content, filename = read_upload(file)
    rule_specs = parse_rule_specs(rules)
    run = create_dataset_from_upload(
        db, content, filename, clean_name, description=description, rules=rule_specs
    )
    return run_to_detail(run)


@router.get("", response_model=Page[DatasetOut])
def list_datasets(
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    total = db.scalar(select(func.count()).select_from(Dataset)) or 0
    rows = db.scalars(
        select(Dataset).order_by(Dataset.id.desc()).limit(limit).offset(offset)
    ).all()
    return Page[DatasetOut](
        items=[DatasetOut.model_validate(r) for r in rows],
        total=total, limit=limit, offset=offset,
    )


@router.get("/{dataset_id}", response_model=DatasetOut)
def get_dataset(dataset_id: int, db: DbSession):
    return DatasetOut.model_validate(get_dataset_or_404(db, dataset_id))


@router.get("/{dataset_id}/profile", response_model=ProfileOut)
def get_profile(dataset_id: int, db: DbSession):
    get_dataset_or_404(db, dataset_id)
    profile = db.scalars(
        select(DatasetProfile)
        .where(DatasetProfile.dataset_id == dataset_id)
        .order_by(DatasetProfile.id.desc())
        .limit(1)
    ).first()
    if profile is None:
        raise NotFoundError("No profile found for this dataset.", {"dataset_id": dataset_id})
    return ProfileOut.model_validate(profile)