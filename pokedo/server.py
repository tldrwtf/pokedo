from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any

app = FastAPI(title="Pokedo Sync Gateway - Dev")

class ChangeItem(BaseModel):
    entity_id: str
    entity_type: str
    action: str
    timestamp: str
    payload: Dict[str, Any]

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/sync")
async def sync(changes: List[ChangeItem]):
    # Minimal validation; later implement LWW/CRDT logic and DB persistence
    processed = []
    for c in changes:
        if c.action not in {"CREATE", "UPDATE", "DELETE"}:
            raise HTTPException(status_code=400, detail=f"Invalid action: {c.action}")
        processed.append({"id": c.entity_id, "entity_type": c.entity_type, "action": c.action})
    return {"result": "success", "processed": processed}
