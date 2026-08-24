from contextlib import contextmanager
from uuid import UUID
from unittest.mock import patch

from outbound_ai.api.auth import Principal, TenantContext
from outbound_ai.api.routers.agent import pending_escalations

ORG = UUID('775bb9b6-5c04-46ff-bdab-0f39e4962eb3')
ACTOR = UUID('11111111-1111-1111-1111-111111111111')

rows = [
    {'escalation_id': 'pending-1', 'organization_id': ORG, 'status': 'PENDING'},
    {'escalation_id': 'pending-2', 'organization_id': ORG, 'status': 'PENDING'},
]

class FakeConnection:
    pass

class FakeDatabase:
    @contextmanager
    def transaction(self, context):
        assert context.organization_id == ORG
        assert context.actor_id == ACTOR
        assert context.actor_role == 'AGENT'
        yield FakeConnection()

principal = Principal(user_id=ACTOR, is_platform_admin=False, role='AGENT')
context = TenantContext(actor_id=ACTOR, organization_id=ORG, actor_role='AGENT')

with patch('outbound_ai.api.routers.agent.tenant_context', return_value=context), \
     patch('outbound_ai.api.routers.agent.get_database', return_value=FakeDatabase()), \
     patch('outbound_ai.api.routers.agent.list_open_escalations', return_value=rows):
    result = pending_escalations(principal=principal, organization_id=ORG)

assert len(result) == 2
assert [item['escalation_id'] for item in result] == ['pending-1', 'pending-2']
print('route_rows=', len(result))
print('route_ids=', [item['escalation_id'] for item in result])
