"""Strict semantic contracts. Financial contracts remain in domain/models.py."""
from typing import Literal, Annotated
from pydantic import Field, model_validator
from app.domain.models import Contract, Metric, Operator, Number, METRIC_INFO, Condition

Text = Annotated[str, Field(min_length=1,max_length=1000)]
class DraftCondition(Contract):
    metric: Metric
    operator: Operator
    value: Number
    unit: Literal['%','x']
    concept: Annotated[str, Field(min_length=1,max_length=200)]
    origin: Literal['user_explicit','llm_interpreted']
    rationale: Text

    @model_validator(mode='after')
    def canonical(self):
        if self.unit != METRIC_INFO[self.metric][1]: raise ValueError('unit mismatch')
        return self

    def condition(self):
        return Condition(**self.model_dump())

class SemanticDraft(Contract):
    universe: Literal['000300.SH']
    conditions: list[DraftCondition] = Field(max_length=30)
    clarifications: list[Text] = Field(max_length=10)
    unsupported_requests: list[Text] = Field(max_length=20)
    compliance_status: Literal['allowed','blocked']

class PatchOperation(Contract):
    operation: Literal['update','remove','enable','disable','add'] = Field(description='暂时不看 means disable; 不考虑/删除 means remove; 再加 means add. Do not emit unchanged conditions.')
    condition_id: str | None
    field: Literal['value','operator'] | None = Field(description='update only: value or operator. ALL other operations: null. Never enabled, metric, or condition.')
    value: Number | Operator | None = Field(description='update only: new threshold number or comparison operator. ALL other operations: null. Never boolean or object.')
    condition: DraftCondition | None = Field(description='add only: full new DraftCondition. update/remove/enable/disable MUST set this to null, never copy the existing condition here.')

    @model_validator(mode='after')
    def shape(self):
        if self.operation=='add':
            if self.condition is None or any(v is not None for v in (self.condition_id,self.field,self.value)): raise ValueError('invalid add')
        else:
            if not self.condition_id or self.condition is not None: raise ValueError('invalid target')
            if self.operation=='update':
                if self.field=='value' and (isinstance(self.value,bool) or not isinstance(self.value,(float,int))): raise ValueError('invalid number')
                if self.field=='operator' and self.value not in ('>','>=','<','<=','=='): raise ValueError('invalid operator')
                if self.field is None: raise ValueError('missing field')
            elif self.field is not None or self.value is not None: raise ValueError('invalid operation')
        return self

class SemanticPatch(Contract):
    operations: list[PatchOperation] = Field(max_length=30)
    clarifications: list[Text] = Field(max_length=10)
    unsupported_requests: list[Text] = Field(max_length=20)
    compliance_status: Literal['allowed','blocked']
