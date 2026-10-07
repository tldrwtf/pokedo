"""Health check and sync endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from pokedo.data.server_models import ServerUser
from pokedo.server.deps import get_current_active_user
from pokedo.server.schemas import ChangeItem

router = APIRouter(tags=["general"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/sync")
def sync(
    changes: list[ChangeItem],
    current_user: Annotated[ServerUser, Depends(get_current_active_user)],
):
    # Minimal validation; LWW/CRDT logic is a future milestone
    processed = []
    for c in changes:
        if c.action not in {"CREATE", "UPDATE", "DELETE"}:
            raise HTTPException(status_code=400, detail=f"Invalid action: {c.action}")
        processed.append({"id": c.entity_id, "entity_type": c.entity_type, "action": c.action})
    return {"result": "success", "processed": processed, "user": current_user.username}
