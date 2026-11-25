import base64
import json
from identity_policy import tenant_user


def principal(tenant='tenant-a', name='person@example.org', auth='aad', extra=None):
    claims = [{'typ': 'tid', 'val': tenant}, {'typ': 'oid', 'val': 'user-id'}]
    if name: claims.append({'typ': 'preferred_username', 'val': name})
    if extra: claims.extend(extra)
    return base64.b64encode(json.dumps({'auth_typ': auth, 'claims': claims}).encode()).decode()


def test_tenant_access():
    assert tenant_user(principal(), 'tenant-a') == 'person@example.org'
    assert tenant_user(principal(tenant='other'), 'tenant-a') is None
    assert tenant_user(principal(), '') is None
    assert tenant_user(None, 'tenant-a') is None
    assert tenant_user('invalid!', 'tenant-a') is None
    assert tenant_user(principal(name=None), 'tenant-a') is None
    assert tenant_user(principal(auth='other'), 'tenant-a') is None
    assert tenant_user(principal(extra=[{'typ':'idtyp','val':'app'}]), 'tenant-a') is None
