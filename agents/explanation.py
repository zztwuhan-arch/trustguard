def explain(assessment, decision):
    if decision.human_required:
        text = 'Your post is awaiting human review. No penalty has been applied by this prototype. '
    else:
        text = 'This review found no supported violation of our prototype financial-scam policy. '
    supported = [e for e in assessment.evidence if e.source == 'content' and e.stance == 'supports' and e.policy_id in ('P1', 'P2')]
    if supported:
        text += 'The following wording needs review: ' + '; '.join(f'“{e.quote}” ({e.policy_id})' for e in supported[:2]) + '. '
    text += 'You may read the prototype policy and request a review with additional context. This is not a finding of criminal fraud.'
    return text
