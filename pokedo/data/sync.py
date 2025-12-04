"""
Sync client for Pokedo (local-first change queue and push to server)

Usage:
- Call `init_changes_table()` during app startup to ensure table exists.
- Use `queue_change(...)` to record local CRUD operations.
- Run `push_changes(server_url)` to POST unsynced changes to server `/sync`.

This module uses SQLModel + a `Change` model stored in the same DB as the app (default: sqlite:///pokedo.db).
"""
from __future__ import annotations

import os
import json
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

import requests
from sqlmodel import Field, SQLModel, create_engine, Session, select
from sqlalchemy import Column
from sqlalchemy.sql.sqltypes import JSON as JSONType

DATABASE_URL = os.getenv("POKEDO_DATABASE_URL", "sqlite:///pokedo.db")
engine = create_engine(DATABASE_URL, echo=False)


class ChangeAction(str):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class Change(SQLModel, table=True):
    __tablename__ = "change"
    __table_args__ = {"extend_existing": True}
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    entity_id: str
    entity_type: str
    action: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONType))
    synced: bool = False


def init_changes_table() -> None:
    SQLModel.metadata.create_all(engine)


def queue_change(entity_id: str, entity_type: str, action: str, payload: Dict[str, Any]) -> str:
    c = Change(entity_id=entity_id, entity_type=entity_type, action=action, payload=payload)
    with Session(engine) as session:
        session.add(c)
        session.commit()
        return c.id


def get_unsynced_changes(limit: int = 100) -> List[Change]:
    with Session(engine) as session:
        q = select(Change).where(Change.synced == False).order_by(Change.timestamp)
        results = session.exec(q).all()
        return results[:limit]


def mark_synced(change_ids: List[str]) -> None:
    if not change_ids:
        return
    with Session(engine) as session:
        q = select(Change).where(Change.id.in_(change_ids))
        items = session.exec(q).all()
        for it in items:
            it.synced = True
            session.add(it)
        session.commit()


def push_changes(server_url: str, batch_size: int = 50, timeout: int = 10) -> Dict[str, Any]:
    """Push unsynced changes to server `/sync` endpoint.

    Returns a dict with keys: pushed (int), failures (int), details (list)
    """
    changes = get_unsynced_changes(limit=batch_size)
    if not changes:
        return {"pushed": 0, "failures": 0, "details": []}

    payload = []
    ids = []
    for c in changes:
        payload.append({
            "entity_id": c.entity_id,
            "entity_type": c.entity_type,
            "action": c.action,
            # Use timezone-aware ISO format (UTC)
            "timestamp": c.timestamp.astimezone(timezone.utc).isoformat(),
            "payload": c.payload,
        })
        ids.append(c.id)

    url = server_url.rstrip("/") + "/sync"
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
    except Exception as exc:
        return {"pushed": 0, "failures": len(payload), "details": [str(exc)]}

    # If server responds with success, mark synced
    try:
        mark_synced(ids)
    except Exception as exc:
        return {"pushed": len(ids), "failures": 0, "details": [f"mark_synced_error: {exc}"]}

    return {"pushed": len(ids), "failures": 0, "details": []}


if __name__ == "__main__":
    import typer

    app = typer.Typer()

    @app.command()
    def init():
        """Initialize the changes table in the configured DB."""
        init_changes_table()
        typer.echo("changes table initialized")

    @app.command()
    def queue(entity_id: str, entity_type: str, action: str, payload: str = "{}"):
        p = json.loads(payload)
        cid = queue_change(entity_id, entity_type, action, p)
        typer.echo(f"queued change: {cid}")

    @app.command()
    def push(url: str):
        r = push_changes(url)
        typer.echo(f"push result: {r}")

    app()
