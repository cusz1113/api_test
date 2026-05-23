#!/usr/bin/env python3
"""generate_html_report.py - 读取报告 JSON + HTML 模板，渲染测试报告
支持两种格式：
  格式A（业务流）：report.json 包含 cases 字段
  格式B（单接口）：report.json 包含 endpoint_results 字段
自动检测格式，无需额外参数。
"""
import json
import sys
import os
import re
from html import escape
from datetime import datetime


def json_hl(obj, indent=2):
    """JSON 语法高亮 — 用不可见Unicode标记区分类型"""
    text = json.dumps(obj, ensure_ascii=False, indent=indent, default=str)
    K1, K2 = '\uE000', '\uE001'  # key
    S1, S2 = '\uE002', '\uE003'  # string value
    N1, N2 = '\uE004', '\uE005'  # number
    B1, B2 = '\uE006', '\uE007'  # bool/null
    text = re.sub(r'"([^"]*)"(\s*:)', K1 + r'"\1"' + K2 + r'\2', text)
    text = re.sub(r': "([^"]*)"', ': ' + S1 + r'"\1"' + S2, text)
    text = re.sub(r': (\d+\.?\d*)', ': ' + N1 + r'\1' + N2, text)
    text = re.sub(r': (true|false|null)', ': ' + B1 + r'\1' + B2, text)
    text = escape(text)
    text = text.replace(K1 + '&quot;', '<span class="jk">&quot;').replace('&quot;' + K2, '&quot;</span>')
    text = text.replace(S1 + '&quot;', '<span class="js">&quot;').replace('&quot;' + S2, '&quot;</span>')
    text = text.replace(N1, '<span class="jn">').replace(N2, '</span>')
    text = text.replace(B1, '<span class="jb">').replace(B2, '</span>')
    return text


def resp_hl(raw_body):
    """响应体 JSON 语法高亮"""
    text = json.dumps(raw_body, ensure_ascii=False, indent=2, default=str) if raw_body else 'null'
    K1, K2 = '\uE000', '\uE001'
    S1, S2 = '\uE002', '\uE003'
    N1, N2 = '\uE004', '\uE005'
    B1, B2 = '\uE006', '\uE007'
    text = re.sub(r'"([^"]*)"(\s*:)', K1 + r'"\1"' + K2 + r'\2', text)
    text = re.sub(r': "([^"]*)"', ': ' + S1 + r'"\1"' + S2, text)
    text = re.sub(r': (\d+\.?\d*)', ': ' + N1 + r'\1' + N2, text)
    text = re.sub(r': (true|false|null)', ': ' + B1 + r'\1' + B2, text)
    text = escape(text)
    text = text.replace(K1 + '&quot;', '<span class="jk">&quot;').replace('&quot;' + K2, '&quot;</span>')
    text = text.replace(S1 + '&quot;', '<span class="js">&quot;').replace('&quot;' + S2, '&quot;</span>')
    text = text.replace(N1, '<span class="jn">').replace(N2, '</span>')
    text = text.replace(B1, '<span class="jb">').replace(B2, '</span>')
    return text


def mask_auth(headers):
    if not headers or not isinstance(headers, dict):
        return headers
    h = dict(headers)
    if 'Authorization' in h and len(h['Authorization']) > 12:
        h['Authorization'] = h['Authorization'][:12] + '***'
    return h


def method_color(method):
    return {'GET': '#00d4ff', 'POST': '#00e676', 'PUT': '#ffab40',
            'DELETE': '#ff5252', 'PATCH': '#b388ff'}.get(method.upper(), '#78909c')


def status_color(code):
    if code and code < 300: return '#00e676'
    if code and code < 500: return '#ffab40'
    return '#ff5252'


def status_icon(status):
    return {'PASS': '✅', 'FAIL': '❌', 'SKIP': '⏭️'}.get(status, '❓')


def build_assertions_html(assertions, field_name='assertion'):
    """构建断言结果 HTML，兼容 assertion(pass) 和 assertions(passed) 两种字段名"""
    if not assertions:
        return ''
    rows = ''
    for a in assertions:
        # 兼容 pass / passed
        passed = a.get('pass', a.get('passed', False))
        ap = '✅' if passed else '❌'
        at = a.get('type', '')
        if at == 'smart_assert':
            # 智能断言：展示 scenario/step_role + purpose + reason
            label = a.get('scenario', a.get('step_role', 'smart'))
            reason = a.get('reason', '')
            d = '%s: %s' % (a.get('purpose', ''), reason)
            rows += '<tr class="smart-row"><td>%s</td><td>🧠 %s</td><td>%s</td></tr>' % (ap, escape(label), escape(d))
        elif at == 'status_code':
            d = "期望 %s → 实际 %s" % (a.get('expected'), a.get('actual'))
            rows += '<tr><td>%s</td><td>%s</td><td>%s</td></tr>' % (ap, escape(at), escape(d))
        elif at == 'body_field':
            d = "%s %s → %s" % (a.get('field', ''), a.get('rule', ''), json.dumps(a.get('actual'), ensure_ascii=False)[:120])
            rows += '<tr><td>%s</td><td>%s</td><td>%s</td></tr>' % (ap, escape(at), escape(d))
        else:
            d = str(a)
            rows += '<tr><td>%s</td><td>%s</td><td>%s</td></tr>' % (ap, escape(at), escape(d))
    return '<div class="sec"><div class="stitle">🧪 断言结果</div><table class="atbl"><tbody>%s</tbody></table></div>' % rows


def build_extracted_html(extracted):
    """构建提取变量 HTML"""
    if not extracted:
        return ''
    rows = ''.join('<tr><td class="vn">%s</td><td>%s</td></tr>' % (escape(k), escape(str(v)[:200])) for k, v in extracted.items())
    return '<div class="sec"><div class="stitle">📤 提取变量</div><table class="vtbl"><tbody>%s</tbody></table></div>' % rows


def build_step_html(step, is_setup=False, scenario=''):
    """构建单个步骤的 HTML 片段
    is_setup: 是否为前置准备步骤
    scenario: 场景标签（单接口用例）
    """
    st = step['status']
    code = step.get('response', {}).get('status_code')
    req = step.get('request', {})
    resp = step.get('response', {})
    # 兼容 assertion / assertions
    assertions = step.get('assertion', step.get('assertions', []))
    extracted = step.get('extracted', {})
    error = step.get('error')
    safe_h = mask_auth(req.get('headers', {}))

    # 前置步骤样式
    cls = 'step setup-step' if is_setup else 'step'
    if st == 'FAIL':
        cls += ' fail'
    elif st == 'SKIP':
        cls += ' skip'

    # 步骤名前缀
    name_prefix = '🔧 ' if is_setup else ''

    # 场景标签
    scenario_tag = ''
    if scenario:
        scenario_tag = '<span class="scenario-tag">%s</span>' % escape(scenario)

    # 断言
    ah = build_assertions_html(assertions)

    # 提取变量
    eh = build_extracted_html(extracted)

    # 错误信息
    erh = ''
    if error:
        erh = '<div class="sec esec"><div class="stitle">⚠️ 错误信息</div><pre class="etxt">%s</pre></div>' % escape(str(error))

    # 响应体高亮
    re_ = resp_hl(resp.get('body'))

    return '''<div class="%(cls)s" data-status="%(st)s">
  <div class="step-hd" onclick="toggleStep(this)">
    <span class="ssi">%(icon)s</span>
    <span class="sno">Step %(step_no)d</span>
    <span class="snm">%(name_prefix)s%(name)s</span>
    %(scenario_tag)s
    <span class="mb" style="background:%(mc)s">%(method)s</span>
    <span class="url" title="%(url)s">%(url)s</span>
    <span class="scb" style="color:%(sc)s">%(code)s</span>
    <span class="stgl">▼</span>
  </div>
  <div class="step-bd">
    <div class="twocol">
      <div class="col">
        <div class="sec"><div class="stitle">📤 请求头</div><pre class="cb">%(headers)s</pre></div>
        <div class="sec"><div class="stitle">📤 请求参数</div><pre class="cb">%(params)s</pre></div>
        <div class="sec"><div class="stitle">📤 请求体</div><pre class="cb">%(body)s</pre></div>
      </div>
      <div class="col">
        <div class="sec"><div class="stitle">📥 响应状态码 <span class="scb" style="color:%(sc)s;font-size:14px">%(code)s</span></div></div>
        <div class="sec"><div class="stitle">📥 响应体 <span class="tgl" onclick="event.stopPropagation();toggleResp(this)">收起</span></div><pre class="cb">%(resp)s</pre></div>
      </div>
    </div>
    %(assertions)s%(extracted)s%(error)s
  </div>
</div>''' % dict(
        cls=cls, st=st,
        icon=status_icon(st),
        step_no=step['step_no'],
        name=escape(step['name']),
        name_prefix=name_prefix,
        scenario_tag=scenario_tag,
        mc=method_color(req.get('method', '')),
        method=escape(req.get('method', '')),
        url=escape(req.get('url', '')),
        code=code if code else '-',
        sc=status_color(code),
        headers=json_hl(safe_h),
        params=json_hl(req.get('params', {})),
        body=json_hl(req.get('body')),
        resp=re_,
        assertions=ah, extracted=eh, error=erh,
    )


def build_case_html(case, ci):
    """构建单个用例的 HTML 片段（业务流格式）"""
    cs = case['status']
    steps_html = '\n'.join(build_step_html(step) for step in case['steps'])

    return '''<div class="case %(status)s" data-status="%(status)s" id="case-%(ci)d">
  <div class="case-hd" onclick="toggleCase(this)">
    <span class="ci-icon">%(icon)s</span>
    <span class="ci-id">%(case_id)s</span>
    <span class="ci-nm">%(name)s</span>
    <span class="ci-pri">%(priority)s</span>
    <span class="ci-stats">
      <span class="cs ps">✅ %(passed)d</span>
      <span class="cs fs">❌ %(failed)d</span>
      <span class="cs ss">⏭️ %(skipped)d</span>
    </span>
    <span class="ci-tgl">▼</span>
  </div>
  <div class="case-bd">%(steps)s</div>
</div>''' % dict(
        status=cs.lower(),
        icon=status_icon(cs),
        ci=ci,
        case_id=escape(case['case_id']),
        name=escape(case['case_name']),
        priority=escape(case.get('priority', '')),
        passed=case.get('passed', 0),
        failed=case.get('failed', 0),
        skipped=case.get('skipped', 0),
        steps=steps_html,
    )


def build_endpoint_html(ep, ci):
    """构建单个接口的 HTML 片段（单接口格式）"""
    cs = ep['status']
    setup_results = ep.get('setup_results', [])
    test_details = ep.get('test_details', [])
    tr = ep.get('test_results', {})

    # Setup steps
    setup_html = ''
    if setup_results:
        setup_steps = '\n'.join(build_step_html(s, is_setup=True) for s in setup_results)
        setup_html = '<div class="setup-section"><div class="setup-label">🔧 前置准备 (%d 步)</div>%s</div>' % (len(setup_results), setup_steps)

    # Test steps
    test_html = '\n'.join(build_step_html(s, scenario=s.get('scenario', '')) for s in test_details)

    # 接口路径标签
    path_tag = '<span class="ci-path"><span class="mb" style="background:%s">%s</span> %s</span>' % (
        method_color(ep.get('method', '')),
        escape(ep.get('method', '')),
        escape(ep.get('path', ''))
    )

    return '''<div class="case %(status)s" data-status="%(status)s" id="ep-%(ci)d">
  <div class="case-hd" onclick="toggleCase(this)">
    <span class="ci-icon">%(icon)s</span>
    %(path_tag)s
    <span class="ci-nm">%(name)s</span>
    <span class="ci-stats">
      <span class="cs ps">✅ %(passed)d</span>
      <span class="cs fs">❌ %(failed)d</span>
      <span class="cs ss">⏭️ %(skipped)d</span>
    </span>
    <span class="ci-tgl">▼</span>
  </div>
  <div class="case-bd">%(setup)s%(test)s</div>
</div>''' % dict(
        status=cs.lower(),
        icon=status_icon(cs),
        ci=ci,
        path_tag=path_tag,
        name=escape(ep.get('name', '')),
        passed=tr.get('passed', 0),
        failed=tr.get('failed', 0),
        skipped=tr.get('skipped', 0),
        setup=setup_html,
        test=test_html,
    )


def detect_format(report):
    """自动检测报告格式：A=业务流, B=单接口汇总, C=单接口独立"""
    if 'endpoint_results' in report:
        return 'B'
    if 'setup_results' in report or 'test_results' in report:
        return 'C'
    return 'A'


def generate_html(report_path, template_path=None):
    """主入口：读取报告数据 + 模板，渲染输出 HTML"""
    if template_path is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        skill_dir = os.path.dirname(script_dir)
        template_path = os.path.join(skill_dir, 'templates', 'report.html')

    with open(report_path, 'r') as f:
        report = json.load(f)

    fmt = detect_format(report)

    with open(template_path, 'r') as f:
        template = f.read()

    if fmt == 'A':
        html = render_format_a(report, template)
    elif fmt == 'B':
        html = render_format_b(report, template)
    else:
        html = render_format_c(report, template)

    # 输出文件名
    basename = os.path.basename(report_path)
    if '_summary.json' in basename:
        output_path = report_path.replace('_summary.json', '_summary.html')
    elif '_report.json' in basename:
        output_path = report_path.replace('_report.json', '_report.html')
    else:
        output_path = report_path.rsplit('.', 1)[0] + '.html'

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    size_kb = os.path.getsize(output_path) / 1024
    print(output_path)
    print('OK format=%s size=%.0fKB' % (fmt, size_kb))


def render_format_a(report, template):
    """渲染业务流报告（格式A）"""
    s = report['summary']
    total = max(s.get('total_steps', 0), 1)

    context = {
        'project': escape(report.get('project', '接口测试')),
        'report_type': 'flow',
        'passed_steps': s.get('passed_steps', 0),
        'failed_steps': s.get('failed_steps', 0),
        'skipped_steps': s.get('skipped_steps', 0),
        'pass_rate': s.get('pass_rate', '0%'),
        'passed_cases': s.get('passed_cases', 0),
        'failed_cases': s.get('failed_cases', 0),
        'total_cases': s.get('total_cases', 0),
        'total_steps': s.get('total_steps', 0),
        'pass_pct': '%.1f' % (s.get('passed_steps', 0) / total * 100),
        'fail_pct': '%.1f' % (s.get('failed_steps', 0) / total * 100),
        'skip_pct': '%.1f' % (s.get('skipped_steps', 0) / total * 100),
        'started_at': report.get('started_at', '')[:19].replace('T', ' '),
        'duration': '%.1f' % report.get('duration_seconds', 0),
        'base_url': escape(report.get('base_url', '')),
        'test_account': escape(report.get('test_account', dict()).get('username', '')),
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }

    cases_html = '\n'.join(build_case_html(case, ci) for ci, case in enumerate(report['cases']))
    context['cases_html'] = cases_html

    html = template
    for key, value in context.items():
        html = html.replace('{{%s}}' % key, str(value))
    return html


def render_format_b(report, template):
    """渲染单接口报告（格式B）"""
    s = report['summary']
    total = max(s.get('total_test_steps', 0), 1)

    context = {
        'project': escape(report.get('project', '接口测试')),
        'report_type': 'single',
        'passed_steps': s.get('passed_steps', 0),
        'failed_steps': s.get('failed_steps', 0),
        'skipped_steps': s.get('skipped_steps', 0),
        'pass_rate': s.get('pass_rate', '0%'),
        'passed_cases': s.get('endpoints_passed', 0),
        'failed_cases': s.get('endpoints_failed', 0),
        'total_cases': s.get('total_endpoints', 0),
        'total_steps': s.get('total_test_steps', 0),
        'pass_pct': '%.1f' % (s.get('passed_steps', 0) / total * 100),
        'fail_pct': '%.1f' % (s.get('failed_steps', 0) / total * 100),
        'skip_pct': '%.1f' % (s.get('skipped_steps', 0) / total * 100),
        'started_at': report.get('started_at', '')[:19].replace('T', ' '),
        'duration': '%.1f' % report.get('duration_seconds', 0),
        'base_url': escape(report.get('base_url', '')),
        'test_account': '',
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }

    eps_html = '\n'.join(build_endpoint_html(ep, ci) for ci, ep in enumerate(report['endpoint_results']))
    context['cases_html'] = eps_html

    html = template
    for key, value in context.items():
        html = html.replace('{{%s}}' % key, str(value))
    return html


def render_format_c(report, template):
    """渲染单接口独立报告（格式C：setup_results + test_results）"""
    s = report.get('summary', {})
    ep = report.get('endpoint', {})
    setup_results = report.get('setup_results', [])
    test_results = report.get('test_results', [])

    passed = s.get('test_passed', 0)
    failed = s.get('test_failed', 0)
    skipped = s.get('test_skipped', 0)
    total = max(passed + failed + skipped, 1)

    # 构造一个伪 endpoint 结构，复用 build_endpoint_html
    pseudo_ep = {
        'method': ep.get('method', ''),
        'path': ep.get('path', ''),
        'name': ep.get('name', ep.get('description', '')),
        'status': 'PASS' if failed == 0 else 'FAIL',
        'setup_results': setup_results,
        'test_details': test_results,
        'test_results': {'passed': passed, 'failed': failed, 'skipped': skipped},
    }

    context = {
        'project': escape(report.get('project', '接口测试')),
        'report_type': 'single',
        'passed_steps': passed,
        'failed_steps': failed,
        'skipped_steps': skipped,
        'pass_rate': '%.0f%%' % (passed / total * 100),
        'passed_cases': 1 if failed == 0 else 0,
        'failed_cases': 0 if failed == 0 else 1,
        'total_cases': 1,
        'total_steps': passed + failed + skipped,
        'pass_pct': '%.1f' % (passed / total * 100),
        'fail_pct': '%.1f' % (failed / total * 100),
        'skip_pct': '%.1f' % (skipped / total * 100),
        'started_at': report.get('executed_at', '')[:19].replace('T', ' '),
        'duration': '',
        'base_url': escape(report.get('base_url', '')),
        'test_account': '',
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }

    eps_html = build_endpoint_html(pseudo_ep, 0)
    context['cases_html'] = eps_html

    html = template
    for key, value in context.items():
        html = html.replace('{{%s}}' % key, str(value))
    return html


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python3 generate_html_report.py <report.json> [template.html]', file=sys.stderr)
        sys.exit(1)
    tpl = sys.argv[2] if len(sys.argv) > 2 else None
    generate_html(sys.argv[1], tpl)
