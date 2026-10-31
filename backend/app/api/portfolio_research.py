"""Authenticated portfolio experiments; saved results are scoped to their actor."""

import json

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.auth import get_authenticated_actor
from app.config import get_db
from app.schemas.portfolio_research import PortfolioResearchRequest
from app.exceptions import NotFoundError, ValidationError
from app.models.portfolio_research import PortfolioExperiment
from app.services.portfolio_research import create_experiment, replay_experiment

router = APIRouter(prefix="/api/v1/portfolio-research", tags=["portfolio-research"])


def _owned(db: Session, experiment_id: str, owner: str) -> PortfolioExperiment:
    item = db.query(PortfolioExperiment).filter_by(experiment_id=experiment_id, owner=owner).first()
    if item is None:
        raise NotFoundError("Portfolio experiment not found")
    return item


def _summary(item: PortfolioExperiment) -> dict:
    return {"experiment_id": item.experiment_id, "name": item.name, "created_at": item.created_at,
            "engine_version": item.engine_version, "snapshot_sha256": item.snapshot_sha256,
            "request": item.snapshot["request"], "metrics": item.result["metrics"]}


@router.post("")
def run_portfolio(request: PortfolioResearchRequest, db: Session = Depends(get_db),
                  owner: str = Depends(get_authenticated_actor)) -> dict:
    try:
        item = create_experiment(db, request, owner)
    except ValueError as exc:
        db.rollback()
        raise ValidationError(str(exc)) from exc
    return _summary(item) | {"result": item.result}


@router.get("")
def list_experiments(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                     db: Session = Depends(get_db), owner: str = Depends(get_authenticated_actor)) -> dict:
    query = db.query(PortfolioExperiment).filter_by(owner=owner)
    return {"total": query.count(), "items": [_summary(item) for item in query.order_by(
        PortfolioExperiment.created_at.desc(), PortfolioExperiment.experiment_id.desc()).offset(offset).limit(limit)]}


@router.get("/{experiment_id}")
def get_experiment(experiment_id: str, db: Session = Depends(get_db),
                   owner: str = Depends(get_authenticated_actor)) -> dict:
    item = _owned(db, experiment_id, owner)
    return _summary(item) | {"result": item.result}


@router.post("/{experiment_id}/replay")
def replay(experiment_id: str, db: Session = Depends(get_db),
           owner: str = Depends(get_authenticated_actor)) -> dict:
    try:
        return replay_experiment(_owned(db, experiment_id, owner))
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc


@router.get("/{experiment_id}/export")
def export_experiment(experiment_id: str, db: Session = Depends(get_db),
                      owner: str = Depends(get_authenticated_actor)) -> Response:
    item = _owned(db, experiment_id, owner)
    # Export verified saved bytes, not a fresh query of potentially revised market data.
    try:
        replay_experiment(item)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    package = {"format": "backing-portfolio-experiment-v1", "experiment_id": item.experiment_id,
               "snapshot_sha256": item.snapshot_sha256, "result_sha256": item.result_sha256,
               "snapshot": item.snapshot, "result": item.result}
    return Response(content=json.dumps(package, ensure_ascii=False, allow_nan=False), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="portfolio-{item.experiment_id}.json"'})
