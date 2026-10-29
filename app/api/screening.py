from fastapi import APIRouter, Depends
from pydantic import Field

from app.api.strategy import RevisionRequest, service
from app.domain.models import SessionSnapshot

router = APIRouter(prefix="/api/strategies", tags=["screening"])


class ExecuteRequest(RevisionRequest):
    refresh_data: bool = Field(default=False, strict=True)
    snapshot_id: str | None = Field(default=None, min_length=1, max_length=200)


@router.post("/{strategy_id}/execute", response_model=SessionSnapshot)
def execute_strategy(strategy_id: str, body: ExecuteRequest, sessions=Depends(service)):
    return sessions.execute(strategy_id, body.expected_revision, refresh_data=body.refresh_data, snapshot_id=body.snapshot_id)
