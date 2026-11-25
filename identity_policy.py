"""Authorize signed-in Entra users from the configured tenant.

App Service Authentication must be enabled to validate and inject the principal.
"""
import base64
import binascii
import json

TENANT_CLAIMS = ('http://schemas.microsoft.com/identity/claims/tenantid', 'tid')
OBJECT_CLAIMS = ('http://schemas.microsoft.com/identity/claims/objectidentifier', 'oid')


def tenant_user(raw, tenant_id):
    if not raw or not tenant_id:
        return None
    try:
        principal = json.loads(base64.b64decode(raw, validate=True))
        if not isinstance(principal, dict) or principal.get('auth_typ', '').lower() != 'aad':
            return None
        claims = principal.get('claims', [])
        if not isinstance(claims, list) or any(not isinstance(c, dict) for c in claims):
            return None
        def values(types):
            return [c.get('val') for c in claims if c.get('typ') in types and isinstance(c.get('val'), str)]
        tenants = values(TENANT_CLAIMS)
        objects = values(OBJECT_CLAIMS)
        # A browser user session has a user name. Do not accept application-only identities.
        names = values(('preferred_username', 'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name', 'name', 'upn', 'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/upn'))
        if len(set(x.lower() for x in tenants)) != 1 or tenants[0].lower() != tenant_id.strip().lower():
            return None
        if not objects or not names or any(x.lower() == 'app' for x in values(('idtyp',))):
            return None
        return names[0]
    except (ValueError, TypeError, binascii.Error, UnicodeDecodeError):
        return None
