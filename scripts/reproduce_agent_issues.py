from unittest.mock import Mock, patch

import outbound_ai.ui.app as ui


def fake_request(method, path, *, token='', organization_id='', **kwargs):
    assert method == 'GET'
    assert path == '/agent/escalations'
    assert token == 'agent-token'
    assert organization_id == '775bb9b6-5c04-46ff-bdab-0f39e4962eb3'
    return [
        {
            'customer_name': 'Customer 1',
            'subject': 'Issue 1',
            'reason': 'Still unresolved',
            'latest_customer_message': 'Not fixed',
            'escalated_at': '2026-08-20T08:10:04+00:00',
            'escalation_id': 'pending-1',
        },
        {
            'customer_name': 'Customer 2',
            'subject': 'Issue 2',
            'reason': 'Still unresolved',
            'latest_customer_message': 'Not fixed',
            'escalated_at': '2026-08-20T08:10:04+00:00',
            'escalation_id': 'pending-2',
        },
    ]


with patch.object(ui, '_request', side_effect=fake_request):
    rows = ui.load_escalations('agent-token', '775bb9b6-5c04-46ff-bdab-0f39e4962eb3')

assert len(rows) == 2
assert rows[0][-1] == 'pending-1'
assert rows[1][-1] == 'pending-2'
print('escalation_refresh_rows=', len(rows))
print('escalation_refresh_ids=', [row[-1] for row in rows])

# Verify the source has separate always-visible agent/calling tabs and a hidden parent for management-only tabs.
source = open('src/outbound_ai/ui/app.py', encoding='utf-8').read()
assert 'with gr.Tabs(visible=False) as management_tabs:' in source
assert 'with gr.Tab("متابعة الحملات"):' in source
assert 'with gr.Tab("المعرفة والمستندات"):' in source
assert 'management_tabs,' in source
print('role_layout_markers=ok')
