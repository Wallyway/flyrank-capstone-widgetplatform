# Embeddable Widget & Lead-Capture Platform

FlyRank internship · backend track · capstone.

A customer defines a widget, gets one line of `<script>`, pastes it on a website this platform has
never seen — and the backend safely catches whatever the public internet sends back: validated,
rate-limited, spam-filtered, enriched with location data, stored, and shown in a dashboard.

Two of the three request paths are public. Anyone can call them, from any origin, at any rate, with
any body. That single fact is what the design is about.

---

## Run it

You need Docker. Nothing else — no keys, no accounts, no `.env` to fill in first.

```bash
git clone https://github.com/Wallyway/flyrank-capstone-widgetplatform.git
cd flyrank-capstone-widgetplatform

docker compose up --build                      # API :8000 · Postgres :5432 · customer site :5500
docker compose exec app python -m scripts.seed # two tenants, three widgets, two API keys
```

The seed prints two API keys. That is the only time they exist in the clear — the database stores
their sha256 hash.

| What | Where |
| --- | --- |
| The customer's website (second origin) | <http://localhost:5500> |
| The owner's dashboard | <http://localhost:8000/dashboard> — paste an API key |
| Interactive API docs | <http://localhost:8000/docs> |
| Tests | `docker compose exec app python -m pytest -q` |

Every setting has a working default; `.env.example` documents all of them, and a `.env` overrides
them if you make one.

---

## Architecture

Three request paths, three different sets of rules. Keeping them apart in your head is what keeps
the code clean.

```
┌─ WIDGET OWNER ─ authenticated with an API key ────────────────────────────────┐
│                                                                               │
│  POST/GET/PATCH/DELETE /api/widgets       ─┐                                  │
│  GET  /api/widgets/{id}/embed              │  tenant_id in every WHERE clause │
│  GET  /api/submissions                     │  another tenant's row → 404      │
│  GET  /api/stats/{overview,by-widget,      │                                  │
│                   geo,timeseries}         ─┘                                  │
│  GET  /dashboard          the owner's page, a pure client of the routes above │
└───────────────────────────────────────────────────────────────────────────────┘

┌─ CUSTOMER WEBSITE ─ any origin, public, cached ───────────────────────────────┐
│                                                                               │
│  <script src="http://localhost:8000/widget.js?id=wgt_demo_signup" async>      │
│         │                                                                     │
│         ├─→ GET /widget.js?id=…            loader     max-age=300             │
│         ├─→ GET /static/widget.v1.js       bundle     max-age=1y, immutable   │
│         └─→ GET /public/widgets/{id}/config config     max-age=60 + ETag → 304│
│                    │                                                          │
│                    └─→ renders inside a shadow root                           │
└───────────────────────────────────────────────────────────────────────────────┘

┌─ WEBSITE VISITOR ─ public, CORS, hostile until proven otherwise ──────────────┐
│                                                                               │
│  OPTIONS /public/submissions   preflight → 204 + Access-Control-*             │
│  POST    /public/submissions                                                  │
│      │                                                                        │
│      ├─ body over 8 KB ─────────────────────────────→ 413                     │
│      ├─ malformed JSON / unknown field / bad type ──→ 400  (never a 500)      │
│      ├─ over the rate limit (per IP, per widget) ───→ 429 + Retry-After       │
│      ├─ honeypot filled ────────────────────────────→ 202, flagged, hidden    │
│      ├─ Idempotency-Key already seen ───────────────→ 200, the original row   │
│      ├─ geo: provider A → provider B → give up ─────  never raises            │
│      ├─ INSERT submission  ─┐                                                 │
│      └─ INSERT job         ─┘ one transaction                     → 201       │
└───────────────────────────────────────────────────────────────────────────────┘

┌─ BACKGROUND WORKER ─ nothing here can slow a visitor down ────────────────────┐
│                                                                               │
│  claim due jobs (FOR UPDATE SKIP LOCKED)                                      │
│      → "email" to the log  →  webhook POST                                    │
│      → failure? retry in 2s, 4s, 8s, 16s                                      │
│      → out of attempts? status='dead' + an ALERT line                         │
└───────────────────────────────────────────────────────────────────────────────┘
```

### Layers

One package per layer. No SQL exists outside `repositories/`, and no HTTP status code is decided
inside one.

```
app/
├── api/            HTTP: routers, request models, the auth dependency
│   ├── widgets.py      authenticated CRUD
│   ├── public.py       loader, bundle, config, submissions, /dashboard
│   ├── dashboard.py    submissions + stats for the owner
│   └── deps.py         API key → tenant
├── services/       logic: what is valid, what is a 404, what gets stored
│   ├── widgets.py  delivery.py  submissions.py  validation.py
│   └── ratelimit.py  geo.py  notifications.py  dashboard.py
├── repositories/   data: every SQL statement in the project
│   └── tenants.py  widgets.py  submissions.py  notifications.py  stats.py
├── middleware/     cors.py (public paths only) · body_limit.py
├── core/           db pool + migration runner · ids/hashing · error handlers
├── static/         widget.v1.js · design-tokens.css · dashboard.html · fonts/ · brand/
└── config.py       every environment variable, one place
migrations/         numbered SQL, applied once and recorded
scripts/seed.py     demo data
testsite/           the "customer website", served on a second origin
tests/              50 deterministic tests
```

---

## The data model

```
tenants ──┬─< api_keys        sha256 hash only, never the key
          ├─< widgets         the config the embed script renders
          └─< submissions     what visitors sent
                    └─< notification_jobs   the side effect, off the request path
```

`tenant_id` is carried on every row a customer can reach and appears in the `WHERE` clause of every
authenticated query. Isolation is enforced in SQL, not remembered by the HTTP layer.

Indexes that exist because a query needs them: `submissions (widget_id, created_at DESC)` and
`(tenant_id, created_at DESC)` for the dashboard, `api_keys (key_hash)` for the one lookup on every
authenticated request, `notification_jobs (status, next_attempt_at)` for the worker's only question,
and a **partial unique index** on `submissions (widget_id, idempotency_key) WHERE idempotency_key IS
NOT NULL` — the key may be absent, but never duplicated.

`widgets.id` is a random opaque string (`wgt_7f3a…`), not a counter: it travels in a public URL, and
an integer would let a stranger walk the whole platform one number at a time.

---

## API

### Owner — `Authorization: Bearer <api key>`

| Method | Path | |
| --- | --- | --- |
| `POST` | `/api/widgets` | `201` · `400` with the offending field named |
| `GET` | `/api/widgets` | this tenant's widgets, nobody else's |
| `GET` `PATCH` `DELETE` | `/api/widgets/{id}` | `200`/`204` · **`404`** for another tenant's id |
| `GET` | `/api/widgets/{id}/embed` | the `<script>` line to paste |
| `GET` | `/api/submissions` | `?widget_id=` `?limit=` `?offset=` `?include_spam=` |
| `GET` | `/api/stats/overview` | totals, last 7 days, spam blocked, % located |
| `GET` | `/api/stats/by-widget` | per widget, including ones with no leads yet |
| `GET` | `/api/stats/geo` | country breakdown |
| `GET` | `/api/stats/timeseries` | `?days=14`, quiet days filled with zeros |

No key → `401`. Another tenant's resource → `404`, deliberately, because a `403` would confirm the
id exists.

### Public

| Method | Path | |
| --- | --- | --- |
| `GET` | `/widget.js?id={id}` | the loader · `max-age=300` |
| `GET` | `/static/widget.v1.js` | the bundle · `max-age=31536000, immutable` |
| `GET` | `/public/widgets/{id}/config` | `max-age=60` + `ETag` → `304` on revalidation |
| `OPTIONS` | `/public/submissions` | preflight → `204` |
| `POST` | `/public/submissions` | see below |

```bash
curl -X POST http://localhost:8000/public/submissions \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: optional-client-generated-string' \
  -d '{"widget_id":"wgt_demo_signup",
       "data":{"email":"ada@example.com","name":"Ada","role":"Engineering"},
       "website":""}'
```

| Outcome | Status |
| --- | --- |
| Stored | `201 {"id":…,"status":"received"}` |
| Same `Idempotency-Key` replayed | `200`, the original row, no second insert |
| Honeypot (`website`) filled | `202` — the bot is told exactly what a person is told |
| Unknown or inactive widget | `404` |
| Malformed, missing, wrong type, too long | `400 {"error":"email: not a valid email address"}` |
| Body over `MAX_BODY_BYTES` | `413` |
| Over the rate limit | `429` + `Retry-After` |
| All geo providers down | still `201`, `geo_status: "unavailable"` |
| Notification fails | still `201` — it never ran on this path |

CORS headers are applied **only** to `/widget.js`, `/static/` and `/public/`. The admin API sends
none at all, so no page on the internet can drive it from a browser.

---

## Design decisions worth defending

**CORS is written by hand, per path.** `CORSMiddleware` is global; this platform needs one set of
rules for the endpoints the whole internet calls and no CORS at all for the owner's API. Thirty
lines in `app/middleware/cors.py` say exactly that, and the preflight is answered there rather than
reaching a route.

**Three cache lifetimes, on purpose.** The bundle URL always serves the same bytes, so it is
immutable for a year and a release ships `widget.v2.js`. The config changes when the owner edits the
widget, so it is 60 seconds plus an ETag built from `config_version`. The loader sits between them:
short enough that a new bundle version reaches browsers in minutes, small enough that re-fetching it
costs nothing.

**The widget lives in a shadow root.** The host page's CSS cannot reach in and the widget's cannot
leak out. `testsite/index.html` proves it by declaring `input { border: 3px dashed red !important }`
and leaving one unprotected input beside the widget for comparison.

**Two failure modes, deliberately different.** Geo enrichment is inline but optional — it runs
before the insert because the answer belongs on the row, so it gets a hard timeout, a provider
chain, and every exception swallowed into a `geo_status`. It can make a submission poorer; it can
never make one fail. The notification is deferred and durable — the request writes a job row in the
same transaction as the submission and returns; a dead SMTP host cannot even *slow down* a
submission.

**Idempotency is enforced by the index, not the lookup.** `ON CONFLICT DO NOTHING` on a partial
unique index means two requests arriving at the same moment still produce one row, which a
check-then-insert would not.

**404 rather than 403 across tenants.** A `403` confirms the id exists. In a multi-tenant system
that is a small information leak with no upside.

**The interface is monochromatic on purpose.** The visual identity follows Expo's design system:
white canvas, `#171717` ink, and colour almost entirely absent from the chrome. Black `#000000` is
reserved for the primary action and nothing else; blue `#0d74ce` is reserved for a link inside a
sentence and nothing else. Focus is a solid 2px edge rather than a coloured glow, cards are flat and
separated by a `#dcdee0` hairline rather than a shadow, and the one near-black surface is used as
contrast — the dashboard's headline tile, the landing's code block — never as a dark theme. One
stylesheet of tokens, `app/static/design-tokens.css`, is the only place those values exist.

**Inter and JetBrains Mono are self-hosted, and the widget downloads neither.** They are served from
`/static/fonts/` with a one-year immutable cache, the same way expo.dev serves its own — no third
party learns who loads a page. The embedded widget is deliberately excluded: it asks for Inter in
its font stack and uses it if the visitor already has it, but it never makes a customer's page
download 70 KB of font. Section 4.3 grades small payloads, and a slow widget is a removed widget.

---

## Limitations — the honest list

- **Rate limiting is in-process.** Counters live in one Python process, so they reset on restart and
  do not span replicas. Two app containers would each allow the full limit. The fix is Redis, and it
  is the first thing this would need to run for real.
- **Fixed window, not sliding.** A burst straddling the window boundary can briefly get through at
  double the rate. Acceptable for a form endpoint; not for a payments API.
- **`TRUST_PROXY_HEADERS=1` in compose.** Inside Docker every request arrives from the gateway
  address, so without it the per-IP limit would see the whole internet as one client. It is only
  safe because the only thing in front is a proxy we run — exposed directly, anyone could walk past
  the limit with one header. It defaults to **off** in code for exactly that reason.
- **The honeypot stops naive bots.** Anything driving a real browser fills the visible fields and
  leaves the hidden one alone. A proof-of-work or CAPTCHA challenge is the next step.
- **The "email" is a log line.** The brief allows it, and what is graded is that its failure changes
  nothing. There is no SMTP integration.
- **The dashboard has no auth session.** The API key is pasted once and kept in `localStorage`. Real
  ownership would want a login, short-lived tokens and key rotation.
- **`geo_status` for a private address is `skipped_private_ip`.** Submissions from localhost are
  never located, which is why the mock providers exist for the demo.
- **The widget's typography is not guaranteed.** It asks for Inter without shipping it, so on a
  machine that does not have Inter installed the widget falls back to the system stack while the
  dashboard shows real Inter. That is a deliberate trade: correct-looking beats fast-loading only
  until you are a guest on someone else's page.
- **One design token is overridden for contrast.** Expo's `error` token is `#eb8e90`, a light rose
  that fails AA as body text on white. It carries the error border here, and the message itself
  stays in `#171717`. Fidelity to a palette is not a reason to make text hard to read.
- **The demo landing links the platform's stylesheet.** A real customer site would not; it does so
  here to show the identity end to end, which means it also depends on the API being up to look
  right. The widget's isolation does not depend on this and is proven separately.
- **No AI is used at runtime**, so the shared requirement about tracking per-call AI cost does not
  apply to this system. It is listed here rather than quietly skipped.

---

## Evidence

[EVIDENCE.md](EVIDENCE.md) has one pasted proof per requirement checkbox — real command output, in
the stage that produced it. [DESIGN.md](DESIGN.md) is the one-page design document written before
the code. [BUILDLOG.md](BUILDLOG.md) is the honest AI-usage log.

## License

MIT — see [LICENSE](LICENSE).
