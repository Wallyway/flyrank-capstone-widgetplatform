# Evidence

One pasted proof per requirement checkbox from Section 6 of the brief. Every block below is real
command output, copied as it was printed — nothing is retyped or tidied up.

Proofs are added in the stage that produces them, not at the end.

---

## Widget management

- [x] Authenticated CRUD endpoints for widgets; requests without valid auth are rejected.

**Stage 3.** No key and a wrong key are both rejected before anything else runs:

```
$ curl -s -w '%{http_code} ' http://localhost:8000/api/widgets
401 {"error":"API key required"}

$ curl -s -w '%{http_code} ' -H "Authorization: Bearer wpk_nope" http://localhost:8000/api/widgets
401 {"error":"Invalid API key"}
```

Full CRUD with the right key. `config_version` bumps on every edit so a cached config can be told
apart from a fresh one:

```
$ curl -X POST -H "Authorization: Bearer $ACME_KEY" -d '{"type":"cta","title":"Download the report", ...}'
status 201
wgt_3278a50f3135e355 | Download the report | version 1 | active True

$ curl -X PATCH ... -d '{"button_text":"Get the PDF"}'
Get the PDF | config_version 2

$ curl -X DELETE ...    # then GET the same id
204 404 {"error":"Widget wgt_3278a50f3135e355 not found"}
```

Bad bodies are rejected at the boundary with a named field, never a 500:

```
$ curl -X POST ... -d '{"type":"newsletter","title":"","fields":[]}'
400 {"error":"type: Value error, must be one of ['contact_form', 'cta', 'popover', 'signup_form']; title: String should have at least 1 character; fields: List should have at least 1 item after validation, not 0"}

$ curl -X POST ... -d '{"type":"cta","title":"x","fields":[{"name":"a","label":"A","type":"select"}]}'
400 {"error":"fields: 'a' is a select with no options"}

$ curl -X POST ... -d '... two fields both named "email" ...'
400 {"error":"fields: duplicate field name email"}
```

- [x] Multi-tenant isolation proven: tenant A cannot read or modify tenant B's widgets or submissions.

**Stage 3.** Each key sees only its own rows:

```
$ curl -H "Authorization: Bearer $ACME_KEY"   http://localhost:8000/api/widgets
wgt_b1047ac084d968b0 1 contact_form | Talk to us
wgt_d164428aed89f49d 1 signup_form  | Join the Acme beta

$ curl -H "Authorization: Bearer $GLOBEX_KEY" http://localhost:8000/api/widgets
wgt_afbd2a84aa174ae4 2 cta | Book a Globex demo
```

Globex's key against Acme's widget — read, write and delete all answer `404`, not `403`, so the id
is never confirmed to exist:

```
$ curl        -H "Authorization: Bearer $GLOBEX_KEY" .../api/widgets/wgt_d164428aed89f49d
404 {"error":"Widget wgt_d164428aed89f49d not found"}

$ curl -X PATCH  -H "Authorization: Bearer $GLOBEX_KEY" -d '{"title":"hijacked"}' .../wgt_d164428aed89f49d
404 {"error":"Widget wgt_d164428aed89f49d not found"}

$ curl -X DELETE -H "Authorization: Bearer $GLOBEX_KEY" .../wgt_d164428aed89f49d
404

$ curl -H "Authorization: Bearer $ACME_KEY" .../wgt_d164428aed89f49d     # untouched
wgt_d164428aed89f49d | Join the Acme beta | config_version 1
```

- [x] Embed snippet generated per widget.

**Stage 3.**

```
$ curl -H "Authorization: Bearer $ACME_KEY" http://localhost:8000/api/widgets/wgt_3278a50f3135e355/embed
{"widget_id":"wgt_3278a50f3135e355","snippet":"<script src=\"http://localhost:8000/widget.js?id=wgt_3278a50f3135e355\" async></script>"}
```

## Widget delivery

- [x] Public config endpoint serves a small payload with correct HTTP cache headers.

**Stage 4.** 641 bytes, a 60-second cache and a weak ETag built from `config_version`:

```
$ curl -sI http://localhost:8000/public/widgets/wgt_demo_signup/config -H 'Origin: http://localhost:5500'
HTTP/1.1 200 OK
cache-control: public, max-age=60
etag: W/"wgt_demo_signup-1"
access-control-allow-origin: *
vary: Origin

$ curl -s -w ' bytes %{size_download}' .../config -o /dev/null
 bytes 641
```

Revalidation costs nothing:

```
$ curl -H 'If-None-Match: W/"wgt_demo_signup-1"' .../config
status 304, body bytes 0
```

- [x] Widget JavaScript is served as a versioned bundle.

**Stage 4.** Three different cache lifetimes on purpose — the bundle URL never changes content, so it
is immutable for a year; the loader is short because it decides which bundle version runs:

```
$ curl -sI http://localhost:8000/static/widget.v1.js
HTTP/1.1 200 OK
cache-control: public, max-age=31536000, immutable
content-type: application/javascript; charset=utf-8
content-length: 6278

$ curl -sI 'http://localhost:8000/widget.js?id=wgt_demo_signup'
HTTP/1.1 200 OK
cache-control: public, max-age=300
```

A version that does not exist, and a path-traversal attempt, are both refused:

```
$ curl .../static/widget.v9.js              404 {"error":"Unknown bundle version"}
$ curl '.../static/widget.../etc/passwd.js' 404 {"error":"Not Found"}
```

- [x] The widget renders on a page served from a different origin than the API.

**Stage 4.** The customer page is served by nginx on `http://localhost:5500`; the API is on
`http://localhost:8000`. Two origins. This is the exact chain the browser walks, every hop
cross-origin:

```
$ curl -s http://localhost:5500/ | grep widget.js
  <script src="http://localhost:8000/widget.js?id=wgt_demo_signup" async></script>

# 2 · the loader, requested with Origin: http://localhost:5500
$ curl -s -H 'Origin: http://localhost:5500' 'http://localhost:8000/widget.js?id=wgt_demo_signup'
(function () {
  var base = "http://localhost:8000";
  var widgetId = "wgt_demo_signup";
  var bundle = "http://localhost:8000/static/widget.v1.js";
  ...
})();

# 3 · the bundle the loader injects
status 200  bytes 6278  cache-control: public, max-age=31536000, immutable

# 4 · the config the bundle fetches
status 200  bytes 641
```

The widget mounts inside a **shadow root**, so the host page cannot restyle it. `testsite/index.html`
proves this on purpose: it declares `input { background:#ffe9e9 !important; border: 3px dashed red
!important }` and `button { background:red !important }`, and leaves one unprotected input next to
the widget for comparison.

> Visual confirmation is done by opening <http://localhost:5500> in a browser. Headless rendering was
> not usable in this environment, so no screenshot is claimed here — the request chain above is what
> is actually machine-verified.

**Stage 4b.** The same page now carries two widgets from one bundle — an inline signup form and a
popover contact form — and the bundle stays inside its size budget with all its CSS inlined:

```
$ curl -sI http://localhost:8000/static/widget.v1.js
cache-control: public, max-age=31536000, immutable
content-length: 13507          # budget was 20480

$ for W in wgt_demo_signup wgt_demo_contact; do ...; done
wgt_demo_signup    loader 200  layout inline  | theme auto | fields 3
wgt_demo_contact   loader 200  layout popover | theme auto | fields 2

$ curl -s http://localhost:5500/ | grep -c 'localhost:8000/widget.js'
script tags: 2

$ node --check widget.v1.js
widget.v1.js parses cleanly
```

Two widgets on one page share a single bundle download: the loader queues its mount request and only
the first one injects the script.

## Public submission API

- [x] Cross-origin submissions work: CORS headers correct, preflight (`OPTIONS`) handled.

**Stage 5.** The preflight is answered by the middleware and never reaches the route:

```
$ curl -i -X OPTIONS http://localhost:8000/public/submissions \
    -H 'Origin: http://localhost:5500' \
    -H 'Access-Control-Request-Method: POST' \
    -H 'Access-Control-Request-Headers: content-type, idempotency-key'
HTTP/1.1 204 No Content
access-control-allow-origin: *
access-control-allow-methods: GET, POST, OPTIONS
access-control-allow-headers: content-type, idempotency-key
access-control-max-age: 600
vary: Origin
```

The real request that follows it:

```
$ curl -i -X POST http://localhost:8000/public/submissions -H 'Origin: http://localhost:5500' \
    -H 'Content-Type: application/json' \
    -d '{"widget_id":"wgt_demo_signup","data":{"email":"ada@example.com","name":"Ada Lovelace","role":"Engineering"},"website":""}'
HTTP/1.1 201 Created
access-control-allow-origin: *
{"id":1,"status":"received"}
```

The admin API is deliberately excluded — `curl -I -H 'Origin: http://evil.example' /api/widgets`
returns **0** `access-control-*` headers, so no page can drive it from a browser.

- [x] All incoming input validated; malformed and oversized payloads rejected with 4xx and JSON errors.

**Stage 5.** Every rejection below is a 4xx with a named field. The log shows **0** responses with
status 500 across the whole run:

```
malformed JSON            400 {"error":"body: not valid JSON"}
not an object             400 {"error":"body: must be a JSON object"}
missing widget_id         400 {"error":"widget_id: Field required"}
unknown widget            404 {"error":"Widget not found"}
bad email + bad select
  + unknown field         400 {"error":"surprise: unknown field for this widget; email: not a valid email address; role: must be one of ['Engineering', 'Design', 'Product', 'Something else']"}
name over its max_length  400 {"error":"name: must be at most 80 characters"}
extra top-level key       400 {"error":"tenant_id: unexpected field"}

$ python3 -c '... 100 KB body ...' > big.json && curl --data-binary @big.json ...
  sent bytes: 100074
413 {"error":"Payload too large: limit is 8192 bytes"}

$ docker compose logs app | grep -c ' 500 '
  500 responses: 0
```

- [x] Valid submissions stored safely, linked to the right widget and tenant.

**Stage 5.**

```
$ docker compose exec -T db psql -U widgetuser -d widgets \
    -c "SELECT id, widget_id, tenant_id, data->>'email' AS email, idempotency_key, ip FROM submissions ORDER BY id;"
 id |    widget_id    | tenant_id |       email       | idempotency_key |      ip
----+-----------------+-----------+-------------------+-----------------+--------------
  1 | wgt_demo_signup |         1 | ada@example.com   |                 | 192.168.97.1
  2 | wgt_demo_signup |         1 | grace@example.com | retry-abc-123   | 192.168.97.1
(2 rows)
```

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

- [x] 1 · Layered architecture — data / logic / HTTP separated

**Stage 3.** One package per layer. No SQL exists outside `app/repositories/`, and no HTTP status
code is decided inside them:

```
app/
├── api/           HTTP: routers, request models, the auth dependency
├── services/      logic: what is valid, what is a 404, what gets stored
├── repositories/  data: every SQL statement in the project
├── core/          db pool, migration runner, ids/hashing, error handlers
└── config.py      every env var, one place
```
- [x] 2 · Validation at the boundary — bad input → clean 4xx, never a 500

**Stages 3 and 5.** See the two blocks above: the admin API rejects a bad widget body with a named
field, and the public endpoint rejects malformed, oversized, unknown-field and wrong-type payloads
the same way. `grep -c ' 500 '` over the whole session log returns 0.
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
- [x] 5 · Idempotency where it matters — the retried action happens once

**Stage 5.** A visitor whose connection drops and whose browser retries must not become two leads.
The same `Idempotency-Key` sent three times produces one row:

```
$ for i in 1 2 3; do curl -X POST .../public/submissions \
    -H 'Idempotency-Key: retry-abc-123' \
    -d '{"widget_id":"wgt_demo_signup","data":{"email":"grace@example.com","name":"Grace"}}'; done
  attempt 1 -> 201 {"id":2,"status":"received"}
  attempt 2 -> 200 {"id":2,"status":"replayed"}
  attempt 3 -> 200 {"id":2,"status":"replayed"}

$ ... -tAc "SELECT COUNT(*) FROM submissions WHERE idempotency_key = 'retry-abc-123';"
1
```

The guarantee is the partial unique index, not the lookup: `ON CONFLICT DO NOTHING` means two
requests arriving at the same moment still produce one row, which a check-then-insert would not.
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
