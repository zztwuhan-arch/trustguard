"""Small-KB retrieval: market filter + signal ranking, retain safeguards and context."""
import re
from pathlib import Path
from .models import Policy

ROOT = Path(__file__).resolve().parents[1]
SIGNAL_POLICY = {'guaranteed_return': 'P1', 'deceptive_solicitation': 'P2',
                 'off_platform': 'P3', 'urgency': 'P4', 'protective_context': 'P5',
                 'authority_claim': 'SG1'}

def retrieve(market, signals):
    if market not in ('Global', 'Singapore'):
        raise ValueError('Unsupported market')
    policies = []
    files = [('global_scam.md', 'Global')]
    if market == 'Singapore':
        files.append(('singapore_scam.md', 'Singapore'))
    for filename, scope in files:
        text = (ROOT / 'policies' / filename).read_text(encoding='utf-8')
        version = re.search(r'^Version: (.+)$', text, re.M).group(1)
        for match in re.finditer(r'^## (\w+) \| ([^\n]+)\n(.*?)(?=^## |\Z)', text, re.M | re.S):
            policies.append(Policy(id=match[1], title=match[2], text=match[3].strip(),
                                   market=scope, version=version))
    if not {'P1', 'P2', 'P5', 'P6'}.issubset({p.id for p in policies}):
        raise ValueError('Incomplete policy bundle')
    relevant = {SIGNAL_POLICY[s] for s in signals if s in SIGNAL_POLICY}
    return sorted(policies, key=lambda p: (p.id not in relevant, p.id))
