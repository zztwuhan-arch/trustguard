from .models import Appeal, Policy
from .workflow import run

def review_appeal(case, text, mode='demo', provider=None):
    if not text.strip():
        raise ValueError('Please provide appeal context')
    # Fresh call and original policy snapshot: no earlier model verdict enters the prompt.
    review = run(case['content'], case['market'], mode, appeal=text, provider=provider,
                 policy_snapshot=[Policy.model_validate(p) for p in case['review']['policies']])
    review.decision.human_required = True
    review.decision.reasons.append('All appeal outcomes require independent human resolution')
    prior = case.get('final_action')
    result = 'verify'
    if not review.validation_errors and not review.assessment.conflicts and not review.assessment.verification_required and review.assessment.confidence >= .8:
        if prior is not None and review.assessment.verdict != 'uncertain':
            result = 'uphold' if prior == review.decision.recommendation else 'overturn'
    return Appeal(text=text, prior_action=prior, review=review, recommendation=result)
