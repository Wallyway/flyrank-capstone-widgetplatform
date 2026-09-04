from typing import Optional

from fastapi import HTTPException

from app import config
from app.core.ids import new_widget_id
from app.repositories.widgets import WidgetsRepository

FIELD_TYPES = {"text", "email", "textarea", "select", "checkbox", "number"}


class WidgetsService:
    def __init__(self, repository: WidgetsRepository):
        self.repository = repository

    def create(self, tenant_id: int, widget: dict) -> dict:
        self.check_fields(widget["fields"])
        return self.repository.create(new_widget_id(), tenant_id, widget)

    def list_all(self, tenant_id: int) -> list[dict]:
        return self.repository.list_for_tenant(tenant_id)

    def get(self, widget_id: str, tenant_id: int) -> dict:
        widget = self.repository.get_for_tenant(widget_id, tenant_id)
        if widget is None:
            # 404 and not 403 on purpose: a 403 would confirm the id exists,
            # which tells another tenant something they should not learn.
            raise HTTPException(status_code=404, detail=f"Widget {widget_id} not found")
        return widget

    def update(self, widget_id: str, tenant_id: int, changes: dict) -> dict:
        if not changes:
            raise HTTPException(status_code=400, detail="No fields to update")
        if "fields" in changes:
            self.check_fields(changes["fields"])
        widget = self.repository.update(widget_id, tenant_id, changes)
        if widget is None:
            raise HTTPException(status_code=404, detail=f"Widget {widget_id} not found")
        return widget

    def delete(self, widget_id: str, tenant_id: int):
        if not self.repository.delete(widget_id, tenant_id):
            raise HTTPException(status_code=404, detail=f"Widget {widget_id} not found")

    def embed_snippet(self, widget_id: str, tenant_id: int) -> dict:
        widget = self.get(widget_id, tenant_id)
        snippet = f'<script src="{config.PUBLIC_BASE_URL}/widget.js?id={widget["id"]}" async></script>'
        return {"widget_id": widget["id"], "snippet": snippet}

    # Pydantic already checked each field's shape. What is left is the part it
    # cannot see: names must be unique, and a select is useless without options.
    def check_fields(self, fields: list[dict]):
        if not fields:
            raise HTTPException(status_code=400, detail="fields: at least one field is required")
        names = [field["name"] for field in fields]
        duplicates = {name for name in names if names.count(name) > 1}
        if duplicates:
            raise HTTPException(status_code=400, detail=f"fields: duplicate field name {sorted(duplicates)[0]}")
        if config.HONEYPOT_FIELD in names:
            raise HTTPException(
                status_code=400,
                detail=f"fields: '{config.HONEYPOT_FIELD}' is reserved for the honeypot",
            )
        for field in fields:
            if field["type"] == "select" and not field.get("options"):
                raise HTTPException(status_code=400, detail=f"fields: '{field['name']}' is a select with no options")
