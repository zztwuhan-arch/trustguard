from pathlib import Path
from streamlit.testing.v1 import AppTest


def test_ui_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setenv('TRUSTGUARD_DB', str(tmp_path/'ui.db'))
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'), default_timeout=15).run()
    assert not app.exception
    next(b for b in app.button if b.label == '分析内容').click().run()
    assert not app.exception
    assert any(m.value == 'REMOVE' for m in app.metric)
    next(t for t in app.text_input if t.label == '审核人').set_value('Reviewer A')
    next(t for t in app.text_area if t.label == '审核理由及核验情况').set_value('Original solicitation confirmed for demo.')
    next(s for s in app.selectbox if s.label == '人工最终结论').select('remove')
    next(c for c in app.checkbox if c.label.startswith('我已检查')).check()
    next(b for b in app.button if b.label == '保存人工结论').click().run()
    assert not app.exception
    next(t for t in app.text_area if t.label.startswith('补充背景')).set_value('This is an educational quotation; please check context.')
    next(b for b in app.button if b.label == '提交申诉').click().run()
    assert not app.exception
    next(t for t in app.text_input if t.label == '审核人').set_value('Reviewer B')
    next(t for t in app.text_area if t.label == '审核理由及核验情况').set_value('Verified classroom context in this simulated review.')
    next(s for s in app.selectbox if s.label == '人工最终结论').select('allow')
    next(c for c in app.checkbox if c.label.startswith('我已检查')).check()
    next(b for b in app.button if b.label == '保存人工结论').click().run()
    assert not app.exception
    from storage import Store, appeal_metrics
    assert appeal_metrics(Store(tmp_path/'ui.db').all())['overturn_rate'] == 1.0
