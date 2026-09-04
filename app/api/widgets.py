from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api.deps import require_tenant
from app.services.widgets import FIELD_TYPES, WidgetsService

router = APIRouter(prefix="/api/widgets", tags=["widgets"])

WIDGET_TYPES = {"signup_form", "contact_form", "cta", "popover"}


class FieldSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=40, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(min_length=1, max_length=80)
    type: str
    required: bool = False
    max_length: Optional[int] = Field(default=None, ge=1, le=5000)
    options: Optional[list[str]] = None

    @field_validator("type")
    @classmethod
    def known_type(cls, value: str) -> str:
        if value not in FIELD_TYPES:
            raise ValueError(f"must be one of {sorted(FIELD_TYPES)}")
        return value


class WidgetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=400)
    fields: list[FieldSpec] = Field(min_length=1, max_length=12)
    button_text: str = Field(default="Submit", min_length=1, max_length=40)
    options: dict = Field(default_factory=dict)

    @field_validator("type")
    @classmethod
    def known_type(cls, value: str) -> str:
        if value not in WIDGET_TYPES:
            raise ValueError(f"must be one of {sorted(WIDGET_TYPES)}")
        return value


class WidgetUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = Field(default=None, min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=400)
    fields: Optional[list[FieldSpec]] = Field(default=None, min_length=1, max_length=12)
    button_text: Optional[str] = Field(default=None, min_length=1, max_length=40)
    options: Optional[dict] = None
    active: Optional[bool] = None


def get_service(request: Request) -> WidgetsService:
    return request.app.state.widgets_service


@router.post("", status_code=201, summary="Create a widget")
def create_widget(
    widget: WidgetCreate,
    service: WidgetsService = Depends(get_service),
    tenant: dict = Depends(require_tenant),
):
    return service.create(tenant["id"], widget.model_dump())


@router.get("", summary="List this tenant's widgets")
def list_widgets(
    service: WidgetsService = Depends(get_service),
    tenant: dict = Depends(require_tenant),
):
    return service.list_all(tenant["id"])


@router.get("/{widget_id}", summary="Get one widget")
def get_widget(
    widget_id: str,
    service: WidgetsService = Depends(get_service),
    tenant: dict = Depends(require_tenant),
):
    return service.get(widget_id, tenant["id"])


@router.patch("/{widget_id}", summary="Update a widget")
def update_widget(
    widget_id: str,
    update: WidgetUpdate,
    service: WidgetsService = Depends(get_service),
    tenant: dict = Depends(require_tenant),
):
    changes = update.model_dump(exclude_unset=True)
    if "fields" in changes:
        changes["fields"] = [field for field in changes["fields"]]
    return service.update(widget_id, tenant["id"], changes)


@router.delete("/{widget_id}", status_code=204, summary="Delete a widget")
def delete_widget(
    widget_id: str,
    service: WidgetsService = Depends(get_service),
    tenant: dict = Depends(require_tenant),
):
    service.delete(widget_id, tenant["id"])


@router.get("/{widget_id}/embed", summary="The one line the customer pastes")
def get_embed(
    widget_id: str,
    service: WidgetsService = Depends(get_service),
    tenant: dict = Depends(require_tenant),
):
    return service.embed_snippet(widget_id, tenant["id"])
