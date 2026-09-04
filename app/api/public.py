import json
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError

from app import config
from app.services.delivery import DeliveryService
from app.services.submissions import SubmissionsService

router = APIRouter(tags=["public"])

STATIC_DIR = Path(__file__).resolve().parents[1] / "static"
VERSION_PATTERN = re.compile(r"^v[0-9]+$")
JS_MEDIA_TYPE = "application/javascript; charset=utf-8"


def get_delivery(request: Request) -> DeliveryService:
    return request.app.state.delivery


def get_submissions(request: Request) -> SubmissionsService:
    return request.app.state.submissions_service


# GET and HEAD: a cached asset should answer a header-only request too.
@router.api_route("/widget.js", methods=["GET", "HEAD"], summary="The loader the embed snippet points at")
def widget_loader(id: str, request: Request):
    delivery = get_delivery(request)
    widget = delivery.get_active(id)
    return Response(
        content=delivery.loader_script(widget),
        media_type=JS_MEDIA_TYPE,
        # Short, because this is the file that decides which bundle version a
        # browser ends up running.
        headers={"Cache-Control": f"public, max-age={config.LOADER_MAX_AGE}"},
    )


@router.api_route("/static/widget.{version}.js", methods=["GET", "HEAD"], summary="The versioned widget bundle")
def widget_bundle(version: str):
    # The version is part of a filesystem path, so it is matched against a
    # pattern rather than trusted.
    if not VERSION_PATTERN.match(version):
        raise HTTPException(status_code=404, detail="Unknown bundle version")
    path = STATIC_DIR / f"widget.{version}.js"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Unknown bundle version")
    return Response(
        content=path.read_text(encoding="utf-8"),
        media_type=JS_MEDIA_TYPE,
        # A given URL always serves the same bytes, so a browser never has to
        # ask about it again. A new release is a new filename.
        headers={"Cache-Control": f"public, max-age={config.BUNDLE_MAX_AGE}, immutable"},
    )


@router.api_route("/public/widgets/{widget_id}/config", methods=["GET", "HEAD"], summary="What the widget renders")
def widget_config(widget_id: str, request: Request):
    delivery = get_delivery(request)
    widget = delivery.get_active(widget_id)
    etag = delivery.config_etag(widget)
    headers = {"Cache-Control": f"public, max-age={config.CONFIG_MAX_AGE}", "ETag": etag}

    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)

    return JSONResponse(delivery.public_config(widget), headers=headers)


class SubmissionEnvelope(BaseModel):
    """Only the outer shape. What goes inside `data` is decided by the widget's
    own field list, which Pydantic cannot know about."""

    widget_id: str = Field(min_length=1, max_length=64)
    data: dict


def client_ip(request: Request) -> str:
    # X-Forwarded-For is trusted only when we are told there is a proxy in
    # front. Trusting it by default would let anyone spoof their way past the
    # per-IP rate limit by sending a header.
    if config.TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


@router.post("/public/submissions", summary="What a visitor sends")
async def create_submission(request: Request):
    # The body is read by hand rather than through a model parameter, so the
    # size limit and a malformed JSON both get the status code they deserve
    # instead of whatever FastAPI would have chosen.
    raw = await request.body()
    if len(raw) > config.MAX_BODY_BYTES:
        raise HTTPException(
            status_code=413, detail=f"Payload too large: limit is {config.MAX_BODY_BYTES} bytes"
        )

    try:
        payload = json.loads(raw or b"")
    except ValueError:
        raise HTTPException(status_code=400, detail="body: not valid JSON")

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="body: must be a JSON object")

    try:
        SubmissionEnvelope.model_validate(payload)
    except ValidationError as exc:
        first = exc.errors()[0]
        field = ".".join(str(part) for part in first["loc"]) or "body"
        raise HTTPException(status_code=400, detail=f"{field}: {first['msg']}")

    context = {
        "ip": client_ip(request),
        "user_agent": request.headers.get("user-agent"),
        "referer": request.headers.get("referer") or request.headers.get("origin"),
        "idempotency_key": request.headers.get("idempotency-key"),
    }

    receipt, status = get_submissions(request).submit(payload, context)
    return JSONResponse(receipt, status_code=status)
