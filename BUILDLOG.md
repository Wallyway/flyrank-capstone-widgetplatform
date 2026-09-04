# Build log

Where AI helped on this capstone, where it was wrong, and what I changed. Appended as the stages
landed, not written at the end.

## Stage 0 — repo skeleton and submission pack

**What AI did.** Drafted `.gitignore`, `.env.example`, `capstone.yaml`, the `EVIDENCE.md` checklist
transcribed from Section 6, and this file.

**What I decided.** Python + FastAPI + Postgres, matching the rest of the track so the layering
conventions carry over instead of being invented again. A separate public repo from the first
commit, per Section 11. `.env` in `.gitignore` *before* the first commit, so no secret has ever been
in the history.

## Stage 1–2 — design, migrations, seed

Writing `DESIGN.md` first was worth it: the "two dependencies, two different failure modes" split —
geo inline and optional, notifications deferred and durable — came out of writing it down, and every
later stage just implemented that sentence.

**Where AI was wrong.** It proposed `list[dict]` as a return annotation on a service method also
named `list`. Inside a class body `list` resolves to the method, so the module failed to import with
`TypeError: 'function' object is not subscriptable`. Caught by the container refusing to boot.
Renamed the method to `list_all`.

## Stage 3 — auth and tenant isolation

**A correction I made against the first draft.** The generated exception handler registered on
`fastapi.HTTPException`. That silently misses Starlette's own `HTTPException`, so a 404 for an
unknown route came back as `{"detail":"Not Found"}` while everything else returned `{"error": …}`.
Found by hitting `/api/nope`. Re-registered on `starlette.exceptions.HTTPException`.

**A design choice AI did not make for me.** Another tenant's widget returns `404`, not `403`. A 403
confirms the id exists, which in a multi-tenant system is a small information leak with no upside.

## Stage 4 / 4b — delivery and the interface layer

`curl -I` returned `405` on every delivery endpoint: FastAPI's `@router.get` registers `GET` only,
and does not add `HEAD` the way plain Starlette routing does. For endpoints whose whole job is
caching — the things a CDN or a monitor probes with `HEAD` — that is a real gap, so they became
`api_route(methods=["GET", "HEAD"])`.

I set a size budget before writing the premium UI: the bundle had to stay under 20 KB with all its
CSS inlined, because Section 4.3 grades small payloads and a nice-looking widget that costs 200 KB
would be trading a graded requirement for a screenshot. It came in at 13.5 KB.

Shadow DOM was my call, not a stylistic one. Anything embeddable is going to land on a page with
hostile CSS; `testsite/index.html` proves the point on purpose by painting every unshielded input
red and dashed.

**What I could not verify the way I wanted.** Headless Chromium would not render in this
environment, so `EVIDENCE.md` claims the request chain (which is machine-checked) and says plainly
that the visual confirmation was done by opening the page — rather than claiming a screenshot that
does not exist.

## Stage 5 — the public endpoint

I did read the CORS middleware line by line, as I said in Stage 0 that I would. The thing worth
checking was that the preflight branch requires `Access-Control-Request-Method` to be present — an
`OPTIONS` without it is not a preflight and must not be answered as one — and that
`Allow-Credentials` is never set, which is what makes `Allow-Origin: *` legal rather than merely
convenient.

The route reads the raw body itself instead of taking a Pydantic parameter. That was deliberate: it
is the only way an oversized body gets a `413` and a malformed one gets a `400` with a message I
chose, rather than whatever FastAPI would have decided.

## Stage 6–7 — abuse protection and enrichment

**Something AI suggested that I rejected.** Trusting `X-Forwarded-For` by default. Anyone can send
that header, so it would have turned the per-IP limit into decoration. It is now off in code and
switched on only in `docker-compose.yml`, where the only thing in front is a proxy we run — with a
comment saying exactly that, and a note in the README's limitations.

The `needs_public_ip` flag on providers is mine. Without it the mock providers would refuse to
answer for localhost, and the deterministic fallback proof the brief asks for would not work at all
from a laptop.

## Stage 8 — the background worker

`FOR UPDATE SKIP LOCKED` when claiming jobs, so a second worker process would take different rows
instead of blocking. Not needed today with one container; it is three words that stop this being a
rewrite later.

The submission and its job are inserted on the same connection, in one transaction. An earlier draft
enqueued after the insert returned, which leaves a window where a crash produces a lead nobody is
ever notified about.

## Stage 9 / 9b — dashboard

**A bug my own evidence caught.** `/api/submissions` reported 24 while `/api/stats/overview` reported
23 — the list included the spam row the stats excluded, and I had already written in `EVIDENCE.md`
that the dashboard leaves spam out. Both now share one `filters()` helper, so the count and the list
cannot disagree, and `?include_spam=true` exists for when the owner does want to look.

I also cut a resize handler that refetched all five endpoints on every resize event. It now debounces
and redraws only the chart, which is the only thing that depends on the width.

The chart is hand-written SVG. Fourteen numbers do not justify a charting library, and the CSP-free
inline version is smaller than the loader for one would be.

## Stage 10 — tests

The three things that make them deterministic rather than merely green were deliberate: no network
(a `DeadProvider` that raises on contact, instead of hoping an API is down), no background tasks
(`TestClient` used without its context manager so the lifespan never starts the worker, and
`tick()` driven by hand with `next_attempt_at` stepped back to now — a 2/4/8-second backoff tested
instantly), and no shared state (a fresh tenant per test that cascades away, plus an autouse fixture
clearing the rate-limit counters, without which test order would decide the result).

50 tests, 0.74s, same result three runs in a row.

## Stage 11 — documentation

The limitations list is the part I would want read first. In-process rate limiting that does not
span replicas, a fixed window that leaks at the boundary, `TRUST_PROXY_HEADERS` on in compose, a
honeypot that only stops naive bots, an "email" that is a log line, and a dashboard with no real
session. All of them are choices with a reason, and all of them would need to change before this
served anyone's traffic for money.

## Stage 12 — the Expo repaint

The brief for this one was "make the visual identity closer to Expo", with a link to a design-system
breakdown. That link turned out to be a client-rendered app: 115 KB of HTML with zero hex values in
it, so neither fetching it nor reading its markup produced a single token. I said so rather than
inventing plausible ones, took the specification from two other references that agree with each
other token for token, and then validated the parts that matter against expo.dev's own HTML — which
is where I confirmed they self-host `inter-latin.woff2` and `jetbrains-mono-latin.woff2` from their
own domain rather than using Google Fonts.

What I took literally: the palette (canvas `#ffffff`, ink `#171717`, body `#60646c`, hairline
`#dcdee0`), the rule that black is only ever a primary action and blue is only ever a link inside a
sentence, the radius scale (8 for buttons and inputs, 12 for cards, pill for badges), flat surfaces
with a hairline instead of a shadow, and display type at weight 600 with heavy negative tracking.
The dashboard's headline number sits on a `#171717` tile, which is the single most recognisable move
in that system.

**Two deliberate deviations, both argued rather than assumed.**

The first is the widget's dark mode. Expo has no dark theme — its dark surfaces are contrast, not a
setting — so the dashboard and the landing are light-only now. But the widget is embedded on pages
nobody here controls, and a white card on a dark blog reads as broken, so it keeps its `theme`
option. Its dark variant uses Expo's own `#171717`, and the CTA inverts to white, because black on
`#171717` would be invisible.

The second is the error colour. Expo's `error` token is `#eb8e90`, which does not clear AA contrast
as body text on white. It carries the border; the message stays in ink. Matching a palette is not a
reason to make an error message hard to read.

**The decision I spent longest on** was the font. Inter is what makes this look like Expo at all,
and self-hosting it is what Expo does. But the widget lands on other people's pages, where Section
4.3 grades payload size and where 70 KB of font is exactly the cost that gets a widget deleted. So
the fonts are self-hosted and used on our own two pages, and the widget asks for Inter in its stack
without ever shipping it. It looks slightly different on a machine without Inter installed, and that
is written down in the README's limitations rather than hidden.

A detail that would have been a silent failure: fonts are fetched in CORS mode even from your own
origin's stylesheet. `/static/` was already in the CORS middleware's public prefixes, so it worked —
but had it not, the browser would have downloaded the file and then discarded it without an error.

I also fixed a bug I had shipped in Stage 4b while I was in there: the widget's checkbox inputs
inherited `width: 100%; height: 44px` from the text-input rule, which makes a checkbox a large grey
slab. No test caught it because no test looks at CSS.

## A mistake worth writing down

In Stage 2 I pasted the seed's output straight into `EVIDENCE.md`, and the seed prints API keys. Two
of them went into the history before I noticed, during the Stage 11 self-check when I grepped my own
repository for `wpk_` and got two hits.

What they actually were: keys to a throwaway local Postgres that has since been destroyed with
`docker compose down -v`, and the database only ever held their sha256 hashes anyway. They grant
nothing to anyone. But "it turned out to be harmless" is not the standard — the standard is that
they should never have been in a commit.

What I did: redacted them in the working tree and left the history alone. Section 11 says not to
force-push over the history before submission, and rewriting six commits to hide two dead strings
would destroy more evidence than it protects. If these had been real credentials the answer would
have been the opposite — rotate first, then rewrite, then ask for help.

What I changed about how I work: the seed's output no longer goes into a document unread. Anything
pasted from a terminal gets a `grep` for the key prefix first.

## Overall

AI wrote a lot of the first draft of most files. Every bug listed above was found by running the
thing, not by reading it — which is the honest summary: it is fast at plausible, and plausible is
not the same as correct. The parts I would defend in an interview are the boundaries, and those came
from the design document, not from a prompt.
