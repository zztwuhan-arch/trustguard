from .models import Decision

CONFIDENCE_THRESHOLD = .80

def decide(assessment, validation_errors):
    reasons = list(validation_errors)
    if assessment.confidence < CONFIDENCE_THRESHOLD:
        reasons.append('Confidence below prototype threshold 0.80')
    if assessment.verdict == 'uncertain':
        reasons.append('Ambiguous policy applicability')
    if assessment.conflicts or any(e.stance == 'contradicts' for e in assessment.evidence):
        reasons.append('Conflicting evidence requires human review')
    reasons.extend(assessment.verification_required)
    if assessment.severity == 'high':
        reasons.append('High severity requires human review')
    recommendation = 'remove' if assessment.verdict == 'violation' and not validation_errors else 'allow'
    if recommendation == 'remove':
        reasons.append('Removal is high impact; a human must approve it')
    return Decision(recommendation=recommendation, human_required=bool(reasons), reasons=reasons)
