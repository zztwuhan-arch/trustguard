from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

Market = Literal['Global', 'Singapore']
Signal = Literal['guaranteed_return', 'deceptive_solicitation', 'off_platform', 'urgency', 'protective_context', 'authority_claim']
Action = Literal['allow', 'warn', 'remove']

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Triage(StrictModel):
    category: Literal['financial_scam', 'other', 'uncertain']
    signals: List[Signal]
    risk_score: float = Field(ge=0, le=1)
    uncertainty: Literal['low', 'medium', 'high']

class Evidence(StrictModel):
    signal: Signal
    policy_id: str
    quote: str = Field(min_length=1, max_length=4000)
    source: Literal['content', 'appeal']
    stance: Literal['supports', 'contradicts', 'context']

class Assessment(StrictModel):
    verdict: Literal['violation', 'benign', 'uncertain']
    confidence: float = Field(ge=0, le=1)
    severity: Literal['low', 'medium', 'high']
    evidence: List[Evidence]
    rationale: str
    conflicts: List[str]
    verification_required: List[str]

class Policy(StrictModel):
    id: str
    title: str
    text: str
    market: Market
    version: str

class Decision(StrictModel):
    recommendation: Action
    human_required: bool
    reasons: List[str]

class Review(StrictModel):
    triage: Triage
    policies: List[Policy]
    assessment: Assessment
    decision: Decision
    explanation: str
    validation_errors: List[str]
    evidence_spans: List[dict]
    mode: str
    model: str
    latency_ms: int
    prompt_version: str = 'prototype-1.0'

class Appeal(StrictModel):
    text: str
    prior_action: Optional[Action]
    review: Review
    recommendation: Literal['uphold', 'overturn', 'verify']
    status: Literal['pending', 'resolved'] = 'pending'
    final_action: Optional[Action] = None
    overturned: Optional[bool] = None
