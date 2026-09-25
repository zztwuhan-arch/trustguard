"""Mechanical grounding: exact source quotes, known policies and compatible signals."""
from .policy import SIGNAL_POLICY

def validate_evidence(assessment, content, appeal, policies):
    errors, spans = [], []
    ids = {p.id for p in policies}
    for index, evidence in enumerate(assessment.evidence):
        source = content if evidence.source == 'content' else appeal
        start = source.find(evidence.quote)
        expected = SIGNAL_POLICY[evidence.signal]
        allowed = {expected}
        if evidence.signal == 'authority_claim' and 'SG1' not in ids:
            allowed = {'P5'}
        if evidence.policy_id not in ids or evidence.policy_id not in allowed:
            errors.append(f'Evidence {index}: unsupported policy/signal mapping')
        if start < 0:
            errors.append(f'Evidence {index}: quote is not in its declared source')
        else:
            spans.append({'index': index, 'source': evidence.source, 'start': start,
                          'end': start + len(evidence.quote), 'quote': evidence.quote,
                          'policy_id': evidence.policy_id, 'stance': evidence.stance})
    if assessment.verdict == 'violation' and not any(
        e.source == 'content' and e.stance == 'supports' and e.policy_id in ('P1', 'P2')
        for e in assessment.evidence
    ):
        errors.append('Violation lacks direct P1/P2 supporting evidence in the original content')
    return errors, spans
