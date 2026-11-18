"""Workspaces: one browser's private projects.

A workspace's id is the `dataset` key that scopes every course, section,
applicant, application and lock row. Access is by the anonymous client id a
browser sends as X-Client-Id: a workspace is only visible to the browser that
created (or imported) it.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import ApplicantModel, CourseModel, LockModel, SectionModel, WorkspaceModel
from .repository import wipe_dataset
from .seed import SEED_LOADERS, seed_dataset

DEFAULT_SETTINGS = {
    "min_gpa": 3.0,
    "min_gpa_uta": 3.3,
    "weights": {
        "grade_weight": 3.0,
        "experience_weight": 2.5,
        "recommendation_weight": 2.0,
        "preference_weight": 2.5,
        "skill_match_weight": 1.0,
        "uta_readiness_bonus": 1.5,
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def create_workspace(db: Session, owner: str, name: str, sample: Optional[str] = None) -> WorkspaceModel:
    if sample is not None and sample not in SEED_LOADERS:
        raise ValueError(f"Unknown sample '{sample}'")
    ws = WorkspaceModel(
        id="ws_" + uuid.uuid4().hex,
        owner=owner,
        name=name.strip() or "Untitled term",
        sample=sample,
        created_at=_now(),
        # A sample comes ready to run; a blank workspace saves settings when the user does.
        settings=dict(DEFAULT_SETTINGS) if sample else None,
        schedule=None,
    )
    db.add(ws)
    db.commit()
    if sample:
        seed_dataset(db, ws.id, source=sample)
    return ws


def list_workspaces(db: Session, owner: str) -> List[WorkspaceModel]:
    return list(db.scalars(
        select(WorkspaceModel).where(WorkspaceModel.owner == owner).order_by(WorkspaceModel.created_at)
    ))


def get_owned(db: Session, workspace_id: str, owner: str) -> Optional[WorkspaceModel]:
    ws = db.get(WorkspaceModel, workspace_id)
    return ws if ws is not None and ws.owner == owner else None


def delete_workspace(db: Session, ws: WorkspaceModel) -> None:
    wipe_dataset(db, ws.id)
    db.delete(ws)
    db.commit()


def reset_sample(db: Session, ws: WorkspaceModel) -> None:
    """Puts a sample workspace back to its original data and settings."""
    if not ws.sample:
        raise ValueError("Only sample workspaces can be reset")
    wipe_dataset(db, ws.id)
    seed_dataset(db, ws.id, source=ws.sample)
    ws.settings = dict(DEFAULT_SETTINGS)
    ws.schedule = None
    db.commit()


def _count(db: Session, model, dataset: str) -> int:
    return db.scalar(select(func.count()).select_from(model).where(model.dataset == dataset)) or 0


def summarize(db: Session, ws: WorkspaceModel) -> dict:
    """What the sidebar and the Getting started checklist need about a workspace."""
    counts = {
        "courses": _count(db, CourseModel, ws.id),
        "sections": _count(db, SectionModel, ws.id),
        "applicants": _count(db, ApplicantModel, ws.id),
        "locks": _count(db, LockModel, ws.id),
    }
    return {
        "id": ws.id,
        "name": ws.name,
        "sample": ws.sample,
        "created_at": ws.created_at,
        "counts": counts,
        "setup": {
            "rules": ws.settings is not None,
            "courses": counts["sections"] > 0,
            "applicants": counts["applicants"] > 0,
            "schedule": ws.schedule is not None,
        },
        "settings": ws.settings or DEFAULT_SETTINGS,
        "finalized_at": (ws.schedule or {}).get("finalized_at"),
    }
