import os
from unittest.mock import Mock, patch

os.environ['SUPABASE_URL'] = 'https://example.supabase.co'
os.environ['SUPABASE_ANON_KEY'] = 'test-anon-key'

import outbound_ai.ui.app as ui

response = Mock()
response.status_code = 200
response.json.return_value = {'access_token': 'agent-token'}

session = {
    'memberships': [
        {'id': 'org-dell', 'name': 'dell', 'slug': 'dell', 'role': 'AGENT'},
    ]
}

with patch.object(ui.requests, 'post', return_value=response), patch.object(ui, '_request', return_value=session):
    outputs = ui.login('agent@example.com', 'password123')

assert outputs[0] == 'agent-token'
assert outputs[5] == 'الدور الحالي: **AGENT**'
assert outputs[6]['visible'] is False, outputs[6]
assert outputs[7]['visible'] is False, outputs[7]
assert outputs[8]['choices'] == ['AGENT'], outputs[8]
assert outputs[9]['visible'] is False, outputs[9]
print('agent_login_role=', outputs[5])
print('admin_panel_visible=', outputs[6]['visible'])
print('platform_controls_visible=', outputs[7]['visible'])
print('management_tabs_visible=', outputs[9]['visible'])
