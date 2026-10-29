from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import Field, model_validator

from app.domain.models import Condition, Contract, SessionSnapshot
from app.services.session_service import SessionService

router = APIRouter(prefix="/api/strategies", tags=["strategy"])


def service(request: Request) -> SessionService:
    return request.app.state.sessions


class CompileRequest(Contract):
    source_text: Annotated[str, Field(min_length=1, max_length=2000)]


class RevisionRequest(Contract):
    expected_revision: int = Field(ge=1)


class EditRequest(RevisionRequest):
    conditions: list[Condition] = Field(max_length=30)

    @model_validator(mode="after")
    def unique_ids(self):
        ids = [c.condition_id for c in self.conditions]
        if len(ids) != len(set(ids)):
            raise ValueError("condition_id 不得重复")
        return self


@router.post("/compile", response_model=SessionSnapshot, status_code=201)
def compile_strategy(body: CompileRequest, sessions=Depends(service)):
    return sessions.create(body.source_text)


@router.get("/{strategy_id}", response_model=SessionSnapshot)
def get_strategy(strategy_id: str, sessions=Depends(service)):
    return sessions.get(strategy_id)


@router.put("/{strategy_id}/conditions", response_model=SessionSnapshot)
def edit_strategy(strategy_id: str, body: EditRequest, sessions=Depends(service)):
    return sessions.update(strategy_id, body.expected_revision, body.conditions)


@router.post("/{strategy_id}/validate", response_model=SessionSnapshot)
def validate_strategy(strategy_id: str, body: RevisionRequest, sessions=Depends(service)):
    return sessions.validate(strategy_id, body.expected_revision)
