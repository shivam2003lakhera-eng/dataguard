from typing import Annotated, Literal

from fastapi import APIRouter, File, Query, UploadFile
from sqlalchemy import func, select

from app.api.deps import (
    CurrentUser,
    DbSession,
    get_dataset_or_404,
    get_run_or_404,
    read_upload,
)
from app.models import Dataset, QualityRun
from app.schemas.common import Page
from app.schemas.run import RunDetail, RunListItem, RunOut, run_to_detail
from app.services.pipeline import run_quality_checks

router = APIRouter(tags=["runs"])

RunStatusFilter = Literal["SUCCESS", "COMPLETED_WITH_ISSUES", "FAILED"]


@router.get("/runs", response_model=Page[RunListItem])
def list_my_runs(
    db: DbSession,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    status: Annotated[RunStatusFilter | None, Query()] = None,
):
    """Every run of every dataset I own, newest first."""
    filters = [Dataset.user_id == user.id]
    if status:
        filters.append(QualityRun.status == status)

    total = db.scalar(
        select(func.count())
        .select_from(QualityRun)
        .join(Dataset, Dataset.id == QualityRun.dataset_id)
        .where(*filters)
    ) or 0
    rows = db.execute(
        select(QualityRun, Dataset.name)
        .join(Dataset, Dataset.id == QualityRun.dataset_id)
        .where(*filters)
        .order_by(QualityRun.id.desc())
        .limit(limit).offset(offset)
    ).all()
    items = [
        RunListItem(**RunOut.model_validate(run).model_dump(), dataset_name=name)
        for run, name in rows
    ]
    return Page[RunListItem](items=items, total=total, limit=limit, offset=offset)


@router.post("/datasets/{dataset_id}/runs", response_model=RunDetail, status_code=201)
def create_run(
    dataset_id: int, file: Annotated[UploadFile, File()], db: DbSession, user: CurrentUser
):
    """Check a newly uploaded file against the dataset's enabled rules.

    V1 does not keep CSV rows, so every run needs a freshly uploaded file.
    """
    get_dataset_or_404(db, dataset_id, user)
    content, filename = read_upload(file)
    return run_to_detail(run_quality_checks(db, dataset_id, content, filename))


@router.get("/datasets/{dataset_id}/runs", response_model=Page[RunOut])
def list_runs(
    dataset_id: int,
    db: DbSession,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    get_dataset_or_404(db, dataset_id, user)
    total = db.scalar(
        select(func.count()).select_from(QualityRun).where(QualityRun.dataset_id == dataset_id)
    ) or 0
    rows = db.scalars(
        select(QualityRun)
        .where(QualityRun.dataset_id == dataset_id)
        .order_by(QualityRun.id.desc())
        .limit(limit).offset(offset)
    ).all()
    return Page[RunOut](
        items=[RunOut.model_validate(r) for r in rows], total=total, limit=limit, offset=offset
    )


@router.get("/runs/{run_id}", response_model=RunDetail)
def get_run(run_id: int, db: DbSession, user: CurrentUser):
    return run_to_detail(get_run_or_404(db, run_id, user))