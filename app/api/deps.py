from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.ids import hash_key
from app.repositories.tenants import TenantsRepository

bearer_scheme = HTTPBearer(auto_error=False, description="An API key printed by seed.py")


def get_tenants(request: Request) -> TenantsRepository:
    return request.app.state.tenants


def require_tenant(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    tenants: TenantsRepository = Depends(get_tenants),
) -> dict:
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise HTTPException(status_code=401, detail="API key required")

    # The key is hashed here and only the digest is ever passed further down,
    # so it cannot end up in a log line or a stack trace from the repository.
    tenant = tenants.find_tenant_by_key_hash(hash_key(credentials.credentials))
    if tenant is None:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return tenant
