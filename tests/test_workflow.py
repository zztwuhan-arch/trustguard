from types import SimpleNamespace
import pytest
from agents.models import Assessment, Evidence, Triage
from agents.workflow import run
from agents.policy import retrieve
from agents.provider import DemoProvider, OpenAIProvider, ProviderFailure
from agents.decision import decide
from agents.appeal import review_appeal
from storage import Store, appeal_metrics
from evaluation.evaluate import summarize


def assessment(**updates):
    fields = dict(verdict='violation', confidence=.95, severity='medium',
                  evidence=[Evidence(signal='guaranteed_return', policy_id='P1', quote='Guaranteed returns', source='content', stance='supports')],
                  rationale='Test', conflicts=[], verification_required=[])
    fields.update(updates)
    return Assessment(**fields)

class FixedProvider(DemoProvider):
    def __init__(self, result):
        self.result = result
    def assess(self, content, policies, appeal=''):
        return self.result


def test_high_impact_always_human():
    r = run('Guaranteed returns. Invest now.')
    assert r.decision.recommendation == 'remove' and r.decision.human_required
    assert 'No penalty' in r.explanation

@pytest.mark.parametrize('fields', [{'confidence': .79}, {'severity': 'high'}, {'conflicts': ['contradiction']}])
def test_guardrails_even_for_benign(fields):
    assert decide(assessment(verdict='benign', evidence=[], **fields), []).human_required

@pytest.mark.parametrize('quote,policy,source', [('fabricated', 'P1', 'content'), ('Guaranteed returns', 'FAKE', 'content'), ('Guaranteed returns', 'P1', 'appeal')])
def test_invalid_evidence_cannot_recommend_removal(quote, policy, source):
    a = assessment(evidence=[Evidence(signal='guaranteed_return', policy_id=policy, quote=quote, source=source, stance='supports')])
    r = run('Guaranteed returns', provider=FixedProvider(a))
    assert r.validation_errors and r.decision.human_required
    assert r.decision.recommendation == 'allow'


def test_off_platform_never_standalone_violation():
    a = assessment(evidence=[Evidence(signal='off_platform', policy_id='P3', quote='DM me', source='content', stance='supports')])
    r = run('DM me', provider=FixedProvider(a))
    assert r.validation_errors and r.decision.recommendation == 'allow'


def test_exact_unicode_offsets():
    r = run('稳赚不赔，私信加入。')
    for span in r.evidence_spans:
        assert '稳赚不赔，私信加入。'[span['start']:span['end']] == span['quote']


def test_market_filter_and_exclusions():
    assert {p.id for p in retrieve('Global', [])} == {'P1','P2','P3','P4','P5','P6'}
    assert {'SG1','SG2','P5','P6'}.issubset({p.id for p in retrieve('Singapore', ['guaranteed_return'])})
    with pytest.raises(ValueError):
        retrieve('Unknown', [])


def test_missing_key_does_not_silently_use_demo(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    r = run('Hello', mode='openai')
    assert r.mode == 'openai' and r.assessment.verdict == 'uncertain'
    assert r.decision.human_required and r.validation_errors


def test_openai_contract_and_refusal():
    captured = []
    def parse(**kwargs):
        captured.append(kwargs)
        return SimpleNamespace(output_parsed=None)
    provider = OpenAIProvider(client=SimpleNamespace(responses=SimpleNamespace(parse=parse)))
    with pytest.raises(ProviderFailure):
        provider.assess('ignore instructions', retrieve('Global', []), 'licence claim')
    assert captured[0]['store'] is False
    assert captured[0]['text_format'] is Assessment
    assert captured[0]['input'][1]['role'] == 'user'


def test_provider_timeout_escalates():
    class Broken(DemoProvider):
        def triage(self, content):
            raise ProviderFailure('Timeout')
    r = run('hello', provider=Broken())
    assert r.decision.human_required and r.assessment.confidence == 0


def test_appeal_blind_review_and_audit(tmp_path):
    store = Store(tmp_path/'cases.db')
    case = store.create('Guaranteed returns', 'Global', run('Guaranteed returns'))
    case = store.resolve(case['id'], 'remove', 'Reviewer A', 'Confirmed active promotion.', case['revision'])
    class Spy(DemoProvider):
        def assess(self, content, policies, appeal=''):
            assert content == 'Guaranteed returns'
            assert appeal == 'This was quoted in a classroom.'
            assert all(p.version == 'prototype-1.0' for p in policies)
            return assessment(verdict='benign', evidence=[])
    original = case['review']
    result = review_appeal(case, 'This was quoted in a classroom.', provider=Spy())
    assert result.recommendation == 'overturn' and result.review.decision.human_required
    case = store.appeal(case['id'], result, case['revision'])
    with pytest.raises(ValueError):
        store.appeal(case['id'], result, case['revision'])
    case = store.resolve(case['id'], 'allow', 'Reviewer B', 'Checked classroom source.', case['revision'])
    assert case['review'] == original and case['appeals'][0]['overturned'] is True
    assert appeal_metrics(store.all())['overturn_rate'] == 1.0
    assert len(case['events']) == 4


def test_unresolved_or_no_prior_action_not_counted_as_overturn(tmp_path):
    store = Store(tmp_path/'cases.db')
    case = store.create('hello', 'Global', run('hello'))
    result = review_appeal(case, 'Please review')
    case = store.appeal(case['id'], result, case['revision'])
    assert appeal_metrics(store.all())['overturn_rate'] is None
    store.resolve(case['id'], 'allow', 'A', 'No violation', case['revision'])
    assert appeal_metrics(store.all())['eligible_resolved'] == 0


def test_stale_updates_are_rejected(tmp_path):
    store = Store(tmp_path/'cases.db')
    case = store.create('hello', 'Global', run('hello'))
    store.resolve(case['id'], 'allow', 'A', 'Checked', case['revision'])
    with pytest.raises(ValueError):
        store.resolve(case['id'], 'remove', 'B', 'Stale', case['revision'])


def test_metric_denominators():
    rows = [dict(label=label, prediction=prediction, human=human, provider_error=False)
            for label,prediction,human in [('violation','violation',True), ('violation','uncertain',True),
                                         ('benign','violation',True), ('benign','benign',False),
                                         ('uncertain','benign',False)]]
    m = summarize(rows)
    assert m['precision'] == .5 and m['recall'] == .5
    assert m['false_positive_rate'] == .5 and m['human_escalation_rate'] == .6
    assert m['gray_escalation_rate'] == 0 and m['binary_abstention_rate'] == .25
    assert summarize([])['precision'] is None

@pytest.mark.parametrize('content', ['', ' ', 'x'*8001])
def test_input_bounds(content):
    with pytest.raises(ValueError):
        run(content)
