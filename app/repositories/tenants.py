from typing import Optional

from psycopg_pool import ConnectionPool


class TenantsRepository:
    def __init__(self, pool: ConnectionPool):
        self.pool = pool

    def create_tenant(self, name: str) -> dict:
        with self.pool.connection() as conn:
            return conn.execute(
                "INSERT INTO tenants (name) VALUES (%s) RETURNING id, name, created_at",
                (name,),
            ).fetchone()

    def find_by_name(self, name: str) -> Optional[dict]:
        with self.pool.connection() as conn:
            return conn.execute(
                "SELECT id, name, created_at FROM tenants WHERE name = %s", (name,)
            ).fetchone()

    def add_api_key(self, tenant_id: int, key_hash: str, label: str = "default") -> dict:
        with self.pool.connection() as conn:
            return conn.execute(
                "INSERT INTO api_keys (tenant_id, key_hash, label) VALUES (%s, %s, %s) "
                "ON CONFLICT (key_hash) DO UPDATE SET label = EXCLUDED.label "
                "RETURNING id, tenant_id, label",
                (tenant_id, key_hash, label),
            ).fetchone()

    # The caller hashes the key first, so the plain key never reaches this layer.
    def find_tenant_by_key_hash(self, key_hash: str) -> Optional[dict]:
        with self.pool.connection() as conn:
            return conn.execute(
                "SELECT t.id, t.name FROM api_keys k "
                "JOIN tenants t ON t.id = k.tenant_id "
                "WHERE k.key_hash = %s",
                (key_hash,),
            ).fetchone()
