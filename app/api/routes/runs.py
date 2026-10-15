from typing import Annotated

from fastapi import APIRouter, File, Query, UploadFile
from sqlalchemy import func, select

from app.api.deps import DbSession, get_dataset_or_404, read_upload
from app.core.exceptions import NotFoundError
from app.models import QualityRun
from app.schemas.common import Page
from app.schemas.run import RunDetail, RunOut, run_to_detail
from app.services.pipeline import run_quality_checks

router = APIRouter(tags=["runs"])


@router.post("/datasets/{dataset_id}/runs", response_model=RunDetail, status_code=201)
def create_run(dataset_id: int, file: Annotated[UploadFile, File()], db: DbSession):
    """Check a newly uploaded file against the dataset's enabled rules.

    V1 does not keep CSV rows, so every run needs a freshly uploaded file.
    """
    get_dataset_or_404(db, dataset_id)
    content, filename = read_upload(file)
    return run_to_detail(run_quality_checks(db, dataset_id, content, filename))


@router.get("/datasets/{dataset_id}/runs", response_model=Page[RunOut])
def list_runs(
    dataset_id: int,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    get_dataset_or_404(db, dataset_id)
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
def get_run(run_id: int, db: DbSession):
    run = db.get(QualityRun, run_id)
    if run is None:
        raise NotFoundError("Run not found.", {"run_id": run_id})
    return run_to_detail(run)