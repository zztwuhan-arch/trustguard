"""Run from project root: python -m evaluation.evaluate --mode demo."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from agents.workflow import run
from storage import Store, appeal_metrics

ROOT = Path(__file__).resolve().parents[1]

def ratio(a, b):
    return a / b if b else None

def summarize(rows):
    binary = [r for r in rows if r['label'] != 'uncertain']
    tp = sum(r['label'] == 'violation' and r['prediction'] == 'violation' for r in binary)
    fp = sum(r['label'] == 'benign' and r['prediction'] == 'violation' for r in binary)
    fn = sum(r['label'] == 'violation' and r['prediction'] != 'violation' for r in binary)
    tn = sum(r['label'] == 'benign' and r['prediction'] != 'violation' for r in binary)
    gray = [r for r in rows if r['label'] == 'uncertain']
    decided = [r for r in binary if r['prediction'] != 'uncertain']
    return {'n': len(rows), 'binary_n': len(binary), 'gray_n': len(gray),
            'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn,
            'precision': ratio(tp, tp+fp), 'recall': ratio(tp, tp+fn),
            'false_positive_rate': ratio(fp, fp+tn),
            'human_escalation_rate': ratio(sum(r['human'] for r in rows), len(rows)),
            'gray_escalation_rate': ratio(sum(r['human'] for r in gray), len(gray)),
            'binary_abstention_rate': ratio(sum(r['prediction'] == 'uncertain' for r in binary), len(binary)),
            'decided_accuracy': ratio(sum(r['prediction'] == r['label'] for r in decided), len(decided)),
            'provider_error_count': sum(r['provider_error'] for r in rows)}

def evaluate(mode='demo', cases_path=None):
    cases = json.loads(Path(cases_path or ROOT / 'data/test_cases.json').read_text(encoding='utf-8'))
    rows = []
    for case in cases:
        review = run(case['content'], case['market'], mode)
        prediction = 'uncertain' if review.validation_errors else review.assessment.verdict
        rows.append({'id': case['id'], 'market': case['market'], 'label': case['label'],
                     'prediction': prediction, 'human': review.decision.human_required,
                     'provider_error': any('Provider failed' in e for e in review.validation_errors),
                     'model': review.model, 'latency_ms': review.latency_ms,
                     'policy_version': sorted({p.version for p in review.policies})})
    return {'generated_at': datetime.now(timezone.utc).isoformat(), 'mode': mode,
            'dataset': 'hand-authored synthetic smoke set; not an independent benchmark',
            'definitions': 'Positive = grounded violation prediction, including human-pending suggestions. Uncertain predictions count as not-positive (FN on positives). Gray labels excluded from binary metrics, included in escalation metrics. No metric measures executed punishment. Null means zero denominator.',
            'metrics': summarize(rows),
            'by_market': {m: summarize([r for r in rows if r['market'] == m]) for m in ('Global', 'Singapore')},
            'rows': rows}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['demo', 'openai'], default='demo')
    parser.add_argument('--cases', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / 'evaluation/latest.json')
    parser.add_argument('--db', type=Path, help='Optional local case DB for observed appeal metrics')
    args = parser.parse_args()
    load_dotenv(ROOT / '.env')
    report = evaluate(args.mode, args.cases)
    report['appeals'] = appeal_metrics(Store(args.db).all()) if args.db else {
        'overturn_rate': None, 'note': 'No live database supplied. Use --db to measure resolved appeals; never synthesize live overturn results.'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report['metrics'], indent=2))
    print(f'Report: {args.output}')

if __name__ == '__main__':
    main()
