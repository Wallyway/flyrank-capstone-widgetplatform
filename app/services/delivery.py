import json

from fastapi import HTTPException

from app import config
from app.repositories.widgets import WidgetsRepository

# Only these keys of a field reach the browser. Anything else the owner stores
# stays on the server side.
PUBLIC_FIELD_KEYS = ("name", "label", "type", "required", "max_length", "options")


class DeliveryService:
    """Builds what the customer's website downloads: the loader and the config."""

    def __init__(self, repository: WidgetsRepository):
        self.repository = repository

    def get_active(self, widget_id: str) -> dict:
        widget = self.repository.get_public(widget_id)
        if widget is None or not widget["active"]:
            raise HTTPException(status_code=404, detail="Widget not found")
        return widget

    def public_config(self, widget: dict) -> dict:
        return {
            "id": widget["id"],
            "version": widget["config_version"],
            "type": widget["type"],
            "title": widget["title"],
            "description": widget["description"],
            "button_text": widget["button_text"],
            "fields": [
                {key: field.get(key) for key in PUBLIC_FIELD_KEYS if field.get(key) is not None}
                for field in widget["fields"]
            ],
            "options": widget["options"],
            "submit_url": f"{config.PUBLIC_BASE_URL}/public/submissions",
            "honeypot_field": config.HONEYPOT_FIELD,
        }

    # Weak ETag: the payload only changes when config_version does, so the
    # browser can revalidate and get a 304 instead of the body again.
    def config_etag(self, widget: dict) -> str:
        return f'W/"{widget["id"]}-{widget["config_version"]}"'

    def loader_script(self, widget: dict) -> str:
        """The tiny file the <script> tag points at.

        It is not the widget. It marks where the widget goes, queues a mount
        request and pulls the versioned bundle once. Being small is what lets it
        have a short cache while the bundle keeps a one-year one.
        """
        bundle_url = f"{config.PUBLIC_BASE_URL}/static/widget.{config.WIDGET_BUNDLE_VERSION}.js"
        return LOADER_TEMPLATE % {
            "base": json.dumps(config.PUBLIC_BASE_URL),
            "widget_id": json.dumps(widget["id"]),
            "bundle": json.dumps(bundle_url),
        }


LOADER_TEMPLATE = """(function () {
  var base = %(base)s;
  var widgetId = %(widget_id)s;
  var bundle = %(bundle)s;

  // Where this script tag sits is where the widget goes.
  var host = document.currentScript;
  var mount = document.createElement("div");
  mount.setAttribute("data-lead-widget", widgetId);
  if (host && host.parentNode) {
    host.parentNode.insertBefore(mount, host.nextSibling);
  } else {
    document.body.appendChild(mount);
  }

  var request = { base: base, widgetId: widgetId, mount: mount };

  // Two widgets on one page must not download the bundle twice, so requests
  // queue up and the bundle drains the queue once it loads.
  if (window.LeadWidget && window.LeadWidget.mount) {
    window.LeadWidget.mount(request);
    return;
  }
  window.__leadWidgetQueue = window.__leadWidgetQueue || [];
  window.__leadWidgetQueue.push(request);
  if (window.__leadWidgetLoading) return;
  window.__leadWidgetLoading = true;

  var script = document.createElement("script");
  script.src = bundle;
  script.async = true;
  (document.head || document.documentElement).appendChild(script);
})();
"""
