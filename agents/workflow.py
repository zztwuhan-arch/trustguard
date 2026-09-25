import time
from .models import Triage, Assessment, Review
from .policy import retrieve
from .provider import DemoProvider, OpenAIProvider, ProviderFailure
from .evidence import validate_evidence
from .decision import decide
from .explanation import explain

def run(content, market='Global', mode='demo', appeal='', provider=None, policy_snapshot=None):
    if not content.strip() or len(content) > 8000 or len(appeal) > 4000:
        raise ValueError('Content must contain 1–8000 characters; appeal at most 4000.')
    if mode not in ('demo', 'openai'):
        raise ValueError('Unsupported mode')
    started = time.perf_counter()
    policies = policy_snapshot if policy_snapshot is not None else retrieve(market, [])
    errors = []
    model = 'unavailable'
    try:
        provider = provider or (DemoProvider() if mode == 'demo' else OpenAIProvider())
        model = provider.model
        triage = provider.triage(content)
        if policy_snapshot is None:
            policies = retrieve(market, triage.signals)
        assessment = provider.assess(content, policies, appeal)
        errors, spans = validate_evidence(assessment, content, appeal, policies)
    except ProviderFailure:
        triage = Triage(category='uncertain', signals=[], risk_score=.5, uncertainty='high')
        assessment = Assessment(verdict='uncertain', confidence=0, severity='low', evidence=[],
                                rationale='Model review unavailable; no conclusion reached.', conflicts=[],
                                verification_required=['Complete manual review; provider unavailable or response invalid.'])
        spans = []
        errors = ['Provider failed; no fallback verdict substituted']
    decision = decide(assessment, errors)
    if triage.uncertainty == 'high':
        decision.human_required = True
        decision.reasons.append('High triage uncertainty')
    if (triage.risk_score >= .8 and assessment.verdict == 'benign') or (triage.risk_score <= .2 and assessment.verdict == 'violation'):
        decision.human_required = True
        decision.reasons.append('Triage and assessment disagree')
    return Review(triage=triage, policies=policies, assessment=assessment, decision=decision,
                  explanation=explain(assessment, decision), validation_errors=errors,
                  evidence_spans=spans, mode=mode, model=model,
                  latency_ms=int((time.perf_counter() - started) * 1000))
