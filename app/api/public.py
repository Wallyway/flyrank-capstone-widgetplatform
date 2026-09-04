import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from app import config
from app.services.delivery import DeliveryService

router = APIRouter(tags=["public"])

STATIC_DIR = Path(__file__).resolve().parents[1] / "static"
VERSION_PATTERN = re.compile(r"^v[0-9]+$")
JS_MEDIA_TYPE = "application/javascript; charset=utf-8"


def get_delivery(request: Request) -> DeliveryService:
    return request.app.state.delivery


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
