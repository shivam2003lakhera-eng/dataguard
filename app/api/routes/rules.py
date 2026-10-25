from fastapi import APIRouter, Response
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, get_dataset_or_404, get_rule_or_404
from app.models import QualityRule
from app.quality.rules.registry import build_rule
from app.schemas.rule import RuleCreate, RuleOut, RuleUpdate

router = APIRouter(tags=["rules"])


@router.get("/datasets/{dataset_id}/rules", response_model=list[RuleOut])
def list_rules(dataset_id: int, db: DbSession, user: CurrentUser):
    get_dataset_or_404(db, dataset_id, user)
    rules = db.scalars(
        select(QualityRule).where(QualityRule.dataset_id == dataset_id).order_by(QualityRule.id)
    ).all()
    return [RuleOut.model_validate(r) for r in rules]


@router.post("/datasets/{dataset_id}/rules", response_model=RuleOut, status_code=201)
def create_rule(dataset_id: int, body: RuleCreate, db: DbSession, user: CurrentUser):
    get_dataset_or_404(db, dataset_id, user)
    build_rule(body.rule_type, body.name, body.configuration, body.severity)  # validates, or raises 422
    rule = QualityRule(
        dataset_id=dataset_id, name=body.name, rule_type=body.rule_type,
        configuration=body.configuration, severity=body.severity.upper(), enabled=body.enabled,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return RuleOut.model_validate(rule)


@router.patch("/rules/{rule_id}", response_model=RuleOut)
def update_rule(rule_id: int, body: RuleUpdate, db: DbSession, user: CurrentUser):
    rule = get_rule_or_404(db, rule_id, user)
    changes = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}

    name = changes.get("name", rule.name)
    configuration = changes.get("configuration", rule.configuration)
    severity = str(changes.get("severity", rule.severity)).upper()
    build_rule(rule.rule_type, name, configuration, severity)  # validate BEFORE saving

    rule.name = name
    rule.configuration = configuration
    rule.severity = severity
    if "enabled" in changes:
        rule.enabled = changes["enabled"]
    db.commit()
    db.refresh(rule)
    return RuleOut.model_validate(rule)


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: int, db: DbSession, user: CurrentUser):
    db.delete(get_rule_or_404(db, rule_id, user))
    db.commit()
    return Response(status_code=204)