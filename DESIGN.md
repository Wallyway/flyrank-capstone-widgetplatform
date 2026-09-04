# Design document

**Problem.** A customer wants to collect leads on a website we do not control, without writing any
backend code. They define a widget once, paste one `<script>` line, and every visitor submission
must arrive here — validated, protected from abuse, enriched, and visible to them alone.

**The shape of the difficulty.** Two of the three request paths are *public*. Anyone can call them,
from any origin, at any rate, with any body. So the design question is not "how do I store a form
submission" — it is "what happens when the input is hostile, the upstream is dead, or the same
request arrives twice".

---

## Data model

Five tables. `tenant_id` is carried on every row a customer can reach, and appears in the `WHERE`
clause of every authenticated query — isolation is enforced in SQL, not in the HTTP layer.

```
tenants ──┬─< api_keys        (key_hash only, never the key itself)
          ├─< widgets         (config the embed script renders)
          └─< submissions     (what visitors sent)
                    └─< notification_jobs   (the side effect, off the request path)
```

| Table | Columns that matter | Indexes |
| --- | --- | --- |
| `tenants` | `id`, `name`, `created_at` | pk |
| `api_keys` | `id`, `tenant_id`, `key_hash` (sha256), `label`, `created_at` | `unique(key_hash)` |
| `widgets` | `id` (`wgt_<rand>`), `tenant_id`, `type`, `title`, `description`, `fields` jsonb, `button_text`, `options` jsonb, `config_version`, `active` | `(tenant_id)` |
| `submissions` | `id`, `widget_id`, `tenant_id`, `data` jsonb, `ip`, `user_agent`, `referer`, `country`, `city`, `geo_provider`, `geo_status`, `is_spam`, `idempotency_key`, `created_at` | `(widget_id, created_at desc)`, `(tenant_id, created_at desc)`, `unique(widget_id, idempotency_key)` |
| `notification_jobs` | `id`, `submission_id`, `status`, `attempts`, `next_attempt_at`, `last_error` | `(status, next_attempt_at)` |

Two choices worth defending:

- **`fields` is jsonb, not a table.** A widget's field list is a *document* the owner edits as a
  whole and the renderer reads as a whole. Normalising it would buy a join and nothing else.
- **`data` is jsonb too.** Submissions must keep exactly what the visitor sent for a schema the
  owner may since have changed. A rigid column set would silently drop history.

`widgets.id` is a random opaque string, not a sequential integer: it appears in a public URL that
anyone can read, so it must not let a stranger enumerate every widget on the platform.

---

## The embed flow

```
1  owner   POST /api/widgets                     → widget created, id = wgt_7f3a…
2  owner   GET  /api/widgets/wgt_7f3a…/embed     → <script src=".../widget.js?id=wgt_7f3a…"></script>
3  visitor browser runs that script
4          GET  /widget.js?id=wgt_7f3a…          → tiny loader, Cache-Control: max-age=300
5          GET  /static/widget.v1.js             → bundle, max-age=31536000, immutable
6          GET  /public/widgets/wgt_7f3a…/config → the config, max-age=60 + ETag
7          bundle renders the form inside a shadow root
8  visitor POST /public/submissions              → 201
```

Three cache lifetimes on purpose. The **bundle** never changes at a given URL, so it is immutable
for a year and a release ships `widget.v2.js`. The **config** changes when the owner edits the
widget, so it is 60 seconds plus an ETag. The **loader** sits between them: short enough that a new
bundle version reaches browsers within minutes, small enough that re-fetching it is free.

---

## API contracts — one per actor

### Path 1 · Owner (authenticated, `Authorization: Bearer <api key>`)

| Method | Path | Returns |
| --- | --- | --- |
| `POST` | `/api/widgets` | `201` the widget · `400` invalid body |
| `GET` | `/api/widgets` | `200` this tenant's widgets only |
| `GET` `PATCH` `DELETE` | `/api/widgets/{id}` | `200`/`204` · **`404` if the widget belongs to another tenant** |
| `GET` | `/api/widgets/{id}/embed` | `200 { "snippet": "<script …></script>" }` |
| `GET` | `/api/submissions` | `200` paginated, filterable by widget |
| `GET` | `/api/stats/{overview,by-widget,geo,timeseries}` | `200` aggregates |

Missing or unknown key → `401`. Another tenant's resource → **`404`, not `403`**: a `403` would
confirm the id exists, which is a small information leak in a multi-tenant system.

### Path 2 · Customer website (public, cached, CORS)

| Method | Path | Returns |
| --- | --- | --- |
| `GET` | `/widget.js?id={id}` | `200 application/javascript` · `404` unknown or inactive widget |
| `GET` | `/static/widget.v1.js` | `200`, immutable |
| `GET` | `/public/widgets/{id}/config` | `200` small JSON + `ETag` · `304` on revalidation · `404` unknown |

### Path 3 · Visitor (public, CORS, protected)

```
POST /public/submissions
Content-Type: application/json
Idempotency-Key: <optional client-generated string>

{ "widget_id": "wgt_7f3a…", "data": { "email": "a@b.com", "name": "Ada" }, "website": "" }
```

| Outcome | Status |
| --- | --- |
| Stored | `201 { "id": …, "status": "received" }` |
| Same `Idempotency-Key` replayed | `200`, the original row, no second insert |
| Honeypot field filled | `202 { "status": "received" }` — the bot is told nothing |
| Unknown / inactive widget | `404` |
| Malformed, missing or too-long fields | `400 { "error": "email: not a valid address" }` |
| Body over `MAX_BODY_BYTES` | `413` |
| Over the rate limit | `429` + `Retry-After` |
| Geo providers all down | still `201`, `geo_status: "unavailable"` |
| Notification fails | still `201` — it never ran on this path |

`OPTIONS /public/submissions` answers the preflight with `204` and the allow headers. CORS is
applied **only** to public paths; the admin API deliberately sends no CORS headers, so no page on
the internet can drive it from a browser at all.

---

## Failure boundaries — the part that is actually designed

Two dependencies are allowed to fail, and each fails in a different way on purpose:

- **Geo enrichment is inline but optional.** It runs before the insert because the result belongs on
  the row, so it gets a hard timeout and a chain: provider A → provider B → give up. Every failure
  is swallowed into a `geo_status` value. It can make a submission *poorer*; it can never make one
  *fail*.
- **The notification is deferred and durable.** It is not attempted during the request at all. The
  request writes a `notification_jobs` row inside the same transaction as the submission and
  returns; a background worker picks it up, retries with exponential backoff, and after
  `NOTIFY_MAX_ATTEMPTS` moves it to dead-letter with an alert log line. A dead SMTP host cannot
  even *slow down* a submission, let alone break one.

---

## Non-goal

**This is not a form builder.** There is no visual editor, no drag-and-drop field designer, and no
template gallery. A widget's `fields` array is authored as JSON through the API. The capstone is
about what happens to a submission after it leaves the browser, and every hour spent on a field
designer is an hour not spent on the boundary that actually gets attacked.

Also explicitly out of scope: a real CDN, a custom domain, hosted deployment, and email delivery to
a real inbox (the "email" is a log line — what is graded is that its failure changes nothing).
