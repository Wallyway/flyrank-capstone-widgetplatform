# Evidence

One pasted proof per requirement checkbox from Section 6 of the brief. Every block below is real
command output, copied as it was printed — nothing is retyped or tidied up.

Proofs are added in the stage that produces them, not at the end.

---

## Widget management

- [ ] Authenticated CRUD endpoints for widgets; requests without valid auth are rejected.
- [ ] Multi-tenant isolation proven: tenant A cannot read or modify tenant B's widgets or submissions.
- [ ] Embed snippet generated per widget.

## Widget delivery

- [ ] Public config endpoint serves a small payload with correct HTTP cache headers.
- [ ] Widget JavaScript is served as a versioned bundle.
- [ ] The widget renders on a page served from a different origin than the API.

## Public submission API

- [ ] Cross-origin submissions work: CORS headers correct, preflight (`OPTIONS`) handled.
- [ ] All incoming input validated; malformed and oversized payloads rejected with 4xx and JSON errors.
- [ ] Valid submissions stored safely, linked to the right widget and tenant.

## Abuse protection

- [ ] Rate limiting returns `429` under a burst — and the API keeps serving legitimate traffic.
- [ ] At least one spam-prevention technique demonstrably blocks a spam submission.

## Enrichment & safe side effects

- [ ] Provider fallback chain: provider A down → provider B answers → submission enriched.
- [ ] All providers down → submission still succeeds (without geo).
- [ ] A failing confirmation email / webhook does not prevent the submission from being stored.

## Documentation

- [ ] README with architecture diagram, setup instructions, and API documentation.

---

## Shared requirements (Section 13)

- [ ] 1 · Layered architecture — data / logic / HTTP separated
- [ ] 2 · Validation at the boundary — bad input → clean 4xx, never a 500
- [ ] 3 · ≥1 background job — off the request path, retries + failure alert
- [ ] 4 · Real persistence — schema as migrations, right indexes, isolated tenants
- [ ] 5 · Idempotency where it matters — the retried action happens once
- [ ] 6 · Secrets clean — env only, hashed if stored, never logged
- [ ] 7 · Cost tracked, if AI is used — no AI at runtime in this system

---

## Acceptance probes (Section 13, Layer 2)

- [ ] PROBE 1 — valid submission from the second-origin page → stored, 2xx, visible in the dashboard
- [ ] PROBE 2 — malformed and oversized payloads → clean 4xx JSON, never a 500
- [ ] PROBE 3 — burst → 429s appear, a normal request right after still succeeds
- [ ] PROBE 4 — provider A down → enriched by B; both down → stored anyway
- [ ] PROBE 5 — side effect throws → submission still returns success and is stored
- [ ] PROBE 6 — honeypot filled → submission silently dropped
