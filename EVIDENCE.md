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
- [x] 4 · Real persistence — schema as migrations, right indexes, isolated tenants

**Stage 2.** `docker compose up` boots the stack, the migration runner applies `001_init.sql` once
and records it, and a restart re-applies nothing.

```
$ docker compose logs app --tail 8
app-1  | INFO:     Started server process [1]
app-1  | INFO:     Waiting for application startup.
app-1  | Server running | db ok | schema up to date
app-1  | INFO:     Application startup complete.
app-1  | INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)

$ curl -s http://localhost:8000/health
{"status":"ok","database":"ok"}

$ docker compose exec -T db psql -U widgetuser -d widgets -c 'SELECT * FROM schema_migrations;'
   version    |          applied_at
--------------+-------------------------------
 001_init.sql | 2026-09-04 18:53:45.321906+00
(1 row)
```

Tables and the indexes the queries actually need:

```
$ docker compose exec -T db psql -U widgetuser -d widgets -c '\dt'
 public | api_keys          | table | widgetuser
 public | notification_jobs | table | widgetuser
 public | schema_migrations | table | widgetuser
 public | submissions       | table | widgetuser
 public | tenants           | table | widgetuser
 public | widgets           | table | widgetuser
(6 rows)

$ ... -c "SELECT tablename, indexname FROM pg_indexes WHERE schemaname='public' ORDER BY 1,2;"
     tablename     |            indexname
-------------------+----------------------------------
 api_keys          | api_keys_key_hash_idx
 api_keys          | api_keys_pkey
 notification_jobs | notification_jobs_due_idx
 notification_jobs | notification_jobs_pkey
 notification_jobs | notification_jobs_submission_idx
 schema_migrations | schema_migrations_pkey
 submissions       | submissions_idempotency_idx
 submissions       | submissions_pkey
 submissions       | submissions_tenant_idx
 submissions       | submissions_widget_idx
 tenants           | tenants_pkey
 widgets           | widgets_pkey
 widgets           | widgets_tenant_idx
(13 rows)
```

The seed creates two tenants so isolation can be tried by hand:

```
$ docker compose exec -T app python seed.py
Acme Analytics  (tenant 1)
  API key: wpk_lJ1ATZRVf-9SQECZv7qyzLGo3Lhp3Tltlhd_iSpocEE
  wgt_d164428aed89f49d  signup_form   Join the Acme beta
  wgt_b1047ac084d968b0  contact_form  Talk to us

Globex Industrial  (tenant 2)
  API key: wpk_QnpTbq0vTr1gcfTKPUns90cPTsXyKbJ0OZr_56ASJuM
  wgt_afbd2a84aa174ae4  cta           Book a Globex demo
```
- [ ] 5 · Idempotency where it matters — the retried action happens once
- [x] 6 · Secrets clean — env only, hashed if stored, never logged

**Stage 2.** The keys printed above are the only time they exist in the clear. The table holds
digests:

```
$ ... -c "SELECT tenant_id, label, left(key_hash, 24) || '...' AS key_hash FROM api_keys;"
 tenant_id | label |          key_hash
-----------+-------+-----------------------------
         1 | seed  | d0032135c2b1a60614437dc3...
         2 | seed  | 4eb7ffd36f327c58d3009b75...
(2 rows)
```
- [ ] 7 · Cost tracked, if AI is used — no AI at runtime in this system

---

## Acceptance probes (Section 13, Layer 2)

- [ ] PROBE 1 — valid submission from the second-origin page → stored, 2xx, visible in the dashboard
- [ ] PROBE 2 — malformed and oversized payloads → clean 4xx JSON, never a 500
- [ ] PROBE 3 — burst → 429s appear, a normal request right after still succeeds
- [ ] PROBE 4 — provider A down → enriched by B; both down → stored anyway
- [ ] PROBE 5 — side effect throws → submission still returns success and is stored
- [ ] PROBE 6 — honeypot filled → submission silently dropped
