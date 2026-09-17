from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AgentRun, Alert, Entity, ExternalItem, Source, User
from ..schemas import PublishRequest
from ..services import dashboard_summary, publish_external_item, run_monitoring
from .deps import current_user, serialize_alert

router = APIRouter(prefix="/api", tags=["radar"])

SEVERITY_ORDER = {"critical": 0, "worth_knowing": 1, "connection": 2, "info": 3}


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(current_user)):
    summary = dashboard_summary(db, user.id)
    recent = list(
        db.execute(
            select(Alert)
            .where(Alert.user_id == user.id)
            .order_by(Alert.created_at.desc())
            .limit(8)
        ).scalars()
    )
    feed = []
    for alert in recent:
        entity = db.get(Entity, alert.entity_id) if alert.entity_id else None
        item = (
            db.get(ExternalItem, alert.external_item_id) if alert.external_item_id else None
        )
        feed.append(serialize_alert(alert, entity, item))
    return {"user": {"id": user.id, "name": user.name}, "summary": summary, "recent": feed}


@router.get("/alerts")
def list_alerts(
    status: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    stmt = select(Alert).where(Alert.user_id == user.id)
    if status:
        stmt = stmt.where(Alert.status == status)
    if severity:
        stmt = stmt.where(Alert.severity == severity)
    alerts = list(db.execute(stmt.order_by(Alert.created_at.desc())).scalars())
    alerts.sort(key=lambda a: (SEVERITY_ORDER.get(a.severity, 9), -a.confidence))
    out = []
    for alert in alerts:
        entity = db.get(Entity, alert.entity_id) if alert.entity_id else None
        item = db.get(ExternalItem, alert.external_item_id) if alert.external_item_id else None
        out.append(serialize_alert(alert, entity, item))
    return {"alerts": out}


@router.get("/alerts/{alert_id}/evidence")
def alert_evidence(
    alert_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    """'Why am I seeing this?' -- the full chain, the checks, and the run trace."""
    alert = db.get(Alert, alert_id)
    if alert is None or alert.user_id != user.id:
        raise HTTPException(status_code=404, detail="alert not found")
    entity = db.get(Entity, alert.entity_id) if alert.entity_id else None
    item = db.get(ExternalItem, alert.external_item_id) if alert.external_item_id else None
    run = db.execute(
        select(AgentRun).where(AgentRun.alert_id == alert.id).order_by(AgentRun.started_at.desc())
    ).scalars().first()
    source = db.get(Source, item.source_id) if item else None
    return {
        "alert": serialize_alert(alert, entity, item),
        "source": (
            {"name": source.name, "url": source.url, "trust_tier": source.trust_tier}
            if source
            else None
        ),
        "agent_trace": run.steps if run else [],
        "run_outcome": run.outcome if run else None,
    }


@router.post("/alerts/{alert_id}/dismiss")
def dismiss(alert_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    alert = db.get(Alert, alert_id)
    if alert is None or alert.user_id != user.id:
        raise HTTPException(status_code=404, detail="alert not found")
    alert.status = "dismissed"
    db.commit()
    return {"id": alert.id, "status": alert.status}


@router.post("/monitor/run")
def monitor_now(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return run_monitoring(db, user.id)


@router.get("/sources")
def sources(db: Session = Depends(get_db)):
    rows = list(db.execute(select(Source).order_by(Source.trust_tier)).scalars())
    return {
        "sources": [
            {
                "id": s.id,
                "name": s.name,
                "kind": s.kind,
                "url": s.url,
                "category": s.category,
                "trust_tier": s.trust_tier,
                "enabled": s.enabled,
                "last_polled_at": s.last_polled_at.isoformat() if s.last_polled_at else None,
            }
            for s in rows
        ]
    }


@router.post("/external/publish")
def publish(body: PublishRequest, db: Session = Depends(get_db)):
    """Inject an outside-world event -- the demo's 'Day 7'."""
    item = publish_external_item(
        db,
        source_name=body.source_name,
        title=body.title,
        body=body.body,
        category=body.category,
        url=body.url,
        metadata=body.metadata,
        trust_tier=body.trust_tier,
    )
    if item is None:
        raise HTTPException(status_code=409, detail="item already recorded")
    return {"id": item.id, "title": item.title}


@router.get("/runs")
def runs(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = list(
        db.execute(
            select(AgentRun)
            .where(AgentRun.user_id == user.id)
            .order_by(AgentRun.started_at.desc())
            .limit(25)
        ).scalars()
    )
    return {
        "runs": [
            {
                "id": r.id,
                "run_type": r.run_type,
                "outcome": r.outcome,
                "alert_id": r.alert_id,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "steps": r.steps or [],
            }
            for r in rows
        ]
    }
