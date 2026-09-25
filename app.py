import json
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv
from agents.workflow import run
from agents.appeal import review_appeal
from storage import Store, appeal_metrics

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env')
st.set_page_config(page_title='TrustGuard · Review Studio', page_icon='🛡️', layout='wide')
st.markdown('''<style>
.block-container {padding-top:4rem;max-width:1250px}
[data-testid="stMetric"] {background:#f0f5f7;padding:18px;border-radius:12px;color:#142c3d}
</style>''', unsafe_allow_html=True)
st.caption('TRUSTGUARD / AI-ASSISTED GOVERNANCE')
st.title('让每一次治理判断，都有依据。')
st.write('Financial Scam Review Studio · Global / Singapore')
st.info('Portfolio prototype · 所有政策均为自拟 prototype，不代表 rednote 或监管机构。所有处置只模拟记录，不操作真实平台。')
store = Store()
with st.sidebar:
    st.subheader('Review settings')
    mode = st.selectbox('运行模式', ['demo', 'openai'], format_func=lambda x: 'Demo · 本地规则，无需 API key' if x == 'demo' else 'OpenAI · 结构化模型分析')
    st.caption('Demo 是有限规则基线，分数不是模型实测或校准概率。')
    consent = True
    if mode == 'openai':
        consent = st.checkbox('允许把本次内容与申诉文本发送给 OpenAI API')
        st.caption('Key 从环境变量读取。请勿输入真实敏感资料。')
    st.divider()
    st.write('01 识别风险 → 02 政策匹配')
    st.write('03 提取证据 → 04 评估风险')
    st.write('05 处置建议 → 06 用户解释')
    st.write('07 申诉复核 → 08 人工审核')
    st.caption('本地单用户演示，无身份认证。案件保存在本地 SQLite。')


def show_review(review):
    a, d = review['assessment'], review['decision']
    cols = st.columns(4)
    cols[0].metric('风险判断', a['verdict'].upper())
    cols[1].metric('置信估计 · 未校准', f"{a['confidence']:.0%}")
    cols[2].metric('处置建议', d['recommendation'].upper())
    cols[3].metric('人工复核', 'REQUIRED' if d['human_required'] else 'OPTIONAL')
    st.caption(f"{review['mode']} / {review['model']} · {review['latency_ms']} ms · {review['prompt_version']}")
    if d['human_required']:
        st.warning('等待人工决定；建议不等于已执行处罚。')
        for reason in d['reasons']:
            st.write('• ' + reason)
    if review['validation_errors']:
        st.error('证据校验未通过，此建议不得作为处罚依据。')
    left, right = st.columns([1.3, 1])
    with left:
        st.subheader('Evidence / 可追溯证据')
        if review['evidence_spans']:
            st.dataframe(review['evidence_spans'], use_container_width=True, hide_index=True)
        else:
            st.write('未找到可引用证据。')
        st.write(a['rationale'])
    with right:
        st.subheader('Policy / 适用政策')
        st.caption('小型知识库全量保留，按信号排序；保留例外条款，避免检索遗漏。')
        for p in review['policies']:
            with st.expander(f"{p['id']} · {p['title']}"):
                st.caption(f"PROTOTYPE · {p['market']} · {p['version']}")
                st.write(p['text'])
    with st.expander('Risk Triage / 原始结构化输出'):
        st.json(review)


analyze_tab, case_tab, metrics_tab = st.tabs(['内容审核', '案件 · 申诉 · 人工复核', '评估与产品说明'])
with analyze_tab:
    examples = json.loads((ROOT / 'data' / 'test_cases.json').read_text(encoding='utf-8'))
    sample_id = st.selectbox('选择演示案例', range(len(examples)), format_func=lambda i: f"{examples[i]['id']} · {examples[i]['title']}")
    example = examples[sample_id]
    with st.form('analyze'):
        market = st.selectbox('适用市场', ['Global', 'Singapore'], index=1 if example['market'] == 'Singapore' else 0, key=f'market_{sample_id}')
        content = st.text_area('待审核内容', value=example['content'], height=150, max_chars=8000, key=f'content_{sample_id}')
        submitted = st.form_submit_button('分析内容', type='primary')
    if submitted:
        if not consent:
            st.error('请先选择是否允许发送至 OpenAI。')
        else:
            try:
                with st.spinner('正在整理证据与政策依据…'):
                    review = run(content, market, mode)
                    case = store.create(content, market, review)
                    st.session_state['active_case'] = case['id']
            except ValueError as exc:
                st.error(str(exc))
    if 'active_case' in st.session_state:
        case = store.get(st.session_state['active_case'])
        st.caption(f"CASE {case['id'][:8]} · {case['market']}")
        st.text(case['content'])
        show_review(case['review'])
        st.subheader('User-facing explanation / 用户看到的初审说明')
        st.write(case['review']['explanation'])
        st.caption('后续申诉与最终人工结论请查看“案件”页。此处保留原始审核快照。')

with case_tab:
    cases = store.all()
    if not cases:
        st.write('先分析一条内容，案件会自动进入这里。')
    else:
        st.caption('所有案件均可查看和请求复核。筛选待处理案件可查看人工队列。')
        pending_only = st.checkbox('只显示待人工处理')
        visible = [c for c in cases if c['status'] in ('pending_human', 'appeal_pending')] if pending_only else cases
        if not visible:
            st.success('当前没有待处理案件。')
        else:
            ids = [c['id'] for c in visible]
            selected = st.selectbox('案件', ids, format_func=lambda cid: next(f"{c['id'][:8]} · {c['status']} · {c['content'][:55]}" for c in visible if c['id'] == cid))
            case = store.get(selected)
            st.text(case['content'])
            st.write(f"状态：{case['status']} · 人工最终结论：{case['final_action'] or '尚无'}")
            with st.expander('原始审核记录'):
                show_review(case['review'])
            pending_appeal = any(a['status'] == 'pending' for a in case['appeals'])
            st.subheader('Appeal / 请求独立复核')
            with st.form(f'appeal_{selected}'):
                appeal_text = st.text_area('补充背景、争议点或材料内容（材料仅视为待核实陈述）', max_chars=4000)
                appeal_submit = st.form_submit_button('提交申诉', disabled=pending_appeal)
            if appeal_submit:
                if not consent:
                    st.error('请先选择是否允许发送至 OpenAI。')
                else:
                    try:
                        with st.spinner('独立复核中…'):
                            result = review_appeal(case, appeal_text, mode)
                            store.appeal(selected, result, case['revision'])
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
            for i, appeal in enumerate(case['appeals']):
                with st.expander(f"申诉 {i+1} · {appeal['status']} · 建议 {appeal['recommendation']}", expanded=appeal['status'] == 'pending'):
                    st.text(appeal['text'])
                    st.write('申诉陈述尚未经外部核实。最终结论必须由人工提交。')
                    show_review(appeal['review'])
                    if appeal['status'] == 'resolved':
                        st.write(f"最终：{appeal['final_action']} · 改判：{appeal['overturned']}")
            st.subheader('Human Review / 模拟审核工作台')
            st.caption('请结合证据、例外条款与材料核验结果填写理由。姓名仅为演示记录，不是身份认证。')
            with st.form(f'human_{selected}'):
                reviewer = st.text_input('审核人')
                action = st.selectbox('人工最终结论', ['allow', 'warn', 'remove'])
                rationale = st.text_area('审核理由及核验情况')
                confirmed = st.checkbox('我已检查原文、政策与申诉材料，并理解此结论仅记录在本地演示中')
                resolve = st.form_submit_button('保存人工结论', disabled=case['status'] == 'resolved')
            if resolve:
                try:
                    if not confirmed:
                        raise ValueError('请先完成复核确认')
                    store.resolve(selected, action, reviewer, rationale, case['revision'])
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
            st.subheader('Audit history / 审核记录')
            st.dataframe(case['events'], use_container_width=True, hide_index=True)
            st.download_button('导出此案件 JSON', json.dumps(case, ensure_ascii=False, indent=2), file_name=f"trustguard-{selected}.json", mime='application/json')

with metrics_tab:
    st.subheader('Live appeal metrics / 本地真实操作记录')
    metrics = appeal_metrics(store.all())
    st.json(metrics)
    st.caption('Overturn rate = 已改判申诉 / 存在前次人工结论的已结申诉；没有适用样本时为 null，不伪造 0%。')
    st.subheader('Evaluation / 可复现评估')
    report_path = ROOT / 'evaluation' / 'baseline_report.json'
    if report_path.exists():
        report = json.loads(report_path.read_text())
        st.caption('固定 synthetic smoke set 的 Demo 基线，不代表 OpenAI 模型、真实流量或生产效果。')
        cols = st.columns(4)
        for col, name in zip(cols, ['precision', 'recall', 'false_positive_rate', 'human_escalation_rate']):
            value = report['metrics'][name]
            col.metric(name, 'N/A' if value is None else f'{value:.1%}')
        with st.expander('完整评估与分市场结果'):
            st.json(report)
    st.markdown('**产品取舍**：删除建议全部升级人工；低置信度保留不确定性；复核不向模型透露原始判断；所有证据都能回到原文。')
    st.markdown('**下一步验证**：独立标注集、多语言与对抗样本、置信度校准、误伤率与审核队列容量、申诉处理时长及用户理解度。')
    st.caption('当前只支持文本、合成样本和单用户本地操作；不验证外部链接，不检测图片，不训练模型。')
