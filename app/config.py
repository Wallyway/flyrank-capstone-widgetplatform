from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://widgetuser:widgetpass@localhost:5432/widgets")

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")

# Which bundle a new embed points at. Shipping new widget code means adding
# widget.v2.js and bumping this; the old URL keeps serving the old file, which
# is what makes caching it for a year safe.
WIDGET_BUNDLE_VERSION = os.getenv("WIDGET_BUNDLE_VERSION", "v1")
BUNDLE_MAX_AGE = int(os.getenv("BUNDLE_MAX_AGE", "31536000"))
LOADER_MAX_AGE = int(os.getenv("LOADER_MAX_AGE", "300"))
CONFIG_MAX_AGE = int(os.getenv("CONFIG_MAX_AGE", "60"))

# Off by default. Turning it on means believing X-Forwarded-For, which is only
# safe when a proxy you control is the one setting it.
TRUST_PROXY_HEADERS = os.getenv("TRUST_PROXY_HEADERS", "0") == "1"

MAX_BODY_BYTES = int(os.getenv("MAX_BODY_BYTES", "8192"))
MAX_FIELD_LENGTH = int(os.getenv("MAX_FIELD_LENGTH", "2000"))

RATE_LIMIT_PER_IP = int(os.getenv("RATE_LIMIT_PER_IP", "10"))
RATE_LIMIT_PER_IP_WINDOW = int(os.getenv("RATE_LIMIT_PER_IP_WINDOW", "60"))
RATE_LIMIT_PER_WIDGET = int(os.getenv("RATE_LIMIT_PER_WIDGET", "60"))
RATE_LIMIT_PER_WIDGET_WINDOW = int(os.getenv("RATE_LIMIT_PER_WIDGET_WINDOW", "60"))
HONEYPOT_FIELD = os.getenv("HONEYPOT_FIELD", "website")

GEO_PROVIDERS = [name.strip() for name in os.getenv("GEO_PROVIDERS", "ipapi,ipapico").split(",") if name.strip()]
GEO_TIMEOUT_SECONDS = float(os.getenv("GEO_TIMEOUT_SECONDS", "2.0"))
GEO_PROVIDER_A_DOWN = os.getenv("GEO_PROVIDER_A_DOWN", "0") == "1"
GEO_PROVIDER_B_DOWN = os.getenv("GEO_PROVIDER_B_DOWN", "0") == "1"
GEO_FORCE_CLIENT_IP = os.getenv("GEO_FORCE_CLIENT_IP", "")

WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
NOTIFY_TIMEOUT_SECONDS = float(os.getenv("NOTIFY_TIMEOUT_SECONDS", "5.0"))
NOTIFY_MAX_ATTEMPTS = int(os.getenv("NOTIFY_MAX_ATTEMPTS", "4"))
NOTIFY_POLL_SECONDS = float(os.getenv("NOTIFY_POLL_SECONDS", "2.0"))
