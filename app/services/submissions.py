from fastapi import HTTPException

from app import config
from app.repositories.submissions import SubmissionsRepository
from app.services.delivery import DeliveryService
from app.services.geo import GeoService
from app.services.ratelimit import RateLimiter
from app.services.validation import validate_submission

ALLOWED_TOP_LEVEL = {"widget_id", "data"}


class SubmissionsService:
    """Everything between "a stranger posted something" and "a row exists"."""

    def __init__(
        self,
        delivery: DeliveryService,
        repository: SubmissionsRepository,
        limiter: RateLimiter,
        geo: GeoService,
    ):
        self.delivery = delivery
        self.repository = repository
        self.limiter = limiter
        self.geo = geo

    def submit(self, payload: dict, context: dict) -> tuple[dict, int]:
        widget = self.delivery.get_active(payload["widget_id"])

        self.reject_unknown_keys(payload)
        data = validate_submission(widget, payload.get("data"))
        self.check_rate_limit(context.get("ip", ""), widget["id"])

        trap = payload.get(config.HONEYPOT_FIELD)
        is_spam = bool(trap and str(trap).strip())

        idempotency_key = context.get("idempotency_key")
        if idempotency_key:
            existing = self.repository.find_by_idempotency_key(widget["id"], idempotency_key)
            if existing:
                return self.receipt(existing, replayed=True), 200

        # Enrichment happens before the insert because the answer belongs on the
        # row. It is allowed to come back empty; it is not allowed to raise.
        location = self.geo.enrich(context.get("ip", ""))

        row = self.repository.create(
            {
                "widget_id": widget["id"],
                "tenant_id": widget["tenant_id"],
                "data": data,
                "ip": context.get("ip"),
                "user_agent": context.get("user_agent"),
                "referer": context.get("referer"),
                "is_spam": is_spam,
                "spam_reason": "honeypot" if is_spam else None,
                "idempotency_key": idempotency_key,
                **location,
            }
        )

        # None means the unique index caught a replay that arrived while the
        # first one was still in flight. Same answer as the check above.
        if row is None:
            row = self.repository.find_by_idempotency_key(widget["id"], idempotency_key)
            return self.receipt(row, replayed=True), 200

        # A bot is told the same thing a person is. It is kept out of the
        # dashboard instead, so nobody learns which field gave them away.
        if is_spam:
            return {"id": row["id"], "status": "received"}, 202

        return self.receipt(row, replayed=False), 201

    def check_rate_limit(self, ip: str, widget_id: str):
        verdict = self.limiter.check(ip, widget_id)
        if verdict is None:
            return
        scope, retry_after = verdict
        raise HTTPException(
            status_code=429,
            detail=f"Too many submissions ({scope} limit). Retry in {retry_after}s.",
            headers={"Retry-After": str(retry_after)},
        )

    def reject_unknown_keys(self, payload: dict):
        """The honeypot key is configurable, so it cannot live in the Pydantic
        model. Everything else at the top level is refused."""
        unexpected = set(payload) - ALLOWED_TOP_LEVEL - {config.HONEYPOT_FIELD}
        if unexpected:
            raise HTTPException(status_code=400, detail=f"{sorted(unexpected)[0]}: unexpected field")

    # The visitor is told nothing about the row beyond that it exists.
    def receipt(self, row: dict, replayed: bool) -> dict:
        return {"id": row["id"], "status": "replayed" if replayed else "received"}
