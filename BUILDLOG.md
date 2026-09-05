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

## Stage 13 — the logo

The mark arrived as a 6.7 MB, 4096x4096 JPEG. Three things had to happen before it could be an
icon, and all three are the sort of thing that gets skipped and then shows up in production:

The **background had to be cut**, but the glyph is white and so is the paper around the squircle, so
a colour key would have erased the mark along with the page. Flood-filling inward from the four
corners removes only what is actually outside the shape.

**A JPEG of a two-tone mark is not two-tone.** It arrived with 3,083 distinct colours of ringing
around every edge, and PNG cannot compress noise: the first 512px export was 212 KB. Rebuilding it
from the luminance channel — snapping the flat areas to the two real colours and keeping a ramp only
where the edge genuinely is — brought the same file to 34 KB with no visible difference.

**The master does not belong in git.** 6.7 MB of source is not a build artifact; `logo.jpg` is
gitignored and only the five derivatives are committed, 49 KB in total.

**What I flagged and did not silently fix.** At 16px this mark is close to unreadable: its stroke is
about 3% of the icon's width where Expo's chevron is about 9%, so at favicon size it lands on half a
pixel and greys out. I said so with the rendered files rather than shipping it quietly, and left the
decision — thicker strokes, or a tighter favicon-only crop — to the person whose design it is.

The customer landing deliberately does **not** carry this logo. That page is pretending to be
someone else's website, and putting our mark on it would undo the one thing it exists to demonstrate.

## Stage 14 — a landing page for the product

"Put the logo on the landing page" had three readings and they led to very different work, so I
asked instead of guessing. The one that was chosen is the one that costs nothing elsewhere: a new
product landing at `/`, with the full identity and the mark, while the test site at :5500 stays
exactly as it was.

That separation matters more than it looks. The test site's entire job is to be a page this platform
does not control — a different origin, with CSS that actively tries to repaint the widget. Turning it
into our own marketing page would have made it prettier and quietly destroyed the thing it exists to
prove. The landing says so in as many words and links across to it, because the widget it embeds is
same-origin and is therefore *not* the CORS proof.

`/` had been a 404 until now, which was a small gap: the one URL a person types first answered
nothing. Both HTML pages now go through one `html_page()` helper with `Cache-Control: no-store`,
since an app shell that reads live data should never be served from a cache.

## Stage 15 — the mark as the hero

Expo builds its homepage around the icon: the mark sits dead centre inside a field of thin radiating
lines with dots on their ends, and the copy arranges itself around it. Adapted here to a centred
layout, the mark sits above the headline rather than beside it, on the same sky wash.

The ray field is generated rather than drawn — 72 rays and 96 dots from a **seeded** random number
generator, so the burst is identical on every build and a reader never sees it shift between
deploys. It is masked with a radial gradient so the field fades out instead of ending at a hard
crop, and it inherits `--ink`, which means it will follow the palette if the palette ever changes.

## Stage 16 — the hero in three columns, and a phone that works

**Layout.** Stacked vertically the mark was decoration sitting above a headline; standing the three
side by side — headline and buttons left, mark centre, status pill and description right — gives it
something to hold up. Below 1140px it collapses to one column, and the pieces are *reordered* rather
than merely narrowed: mark, headline, pill, description, buttons. That needed `display: contents` on
the two wrappers so each child could be placed individually instead of moving as a block.

**The field.** 132 rays and 320 dots now, from a seeded generator, with the dots scattered *along*
each ray rather than only at its tip — that is what stops it reading as a wheel of spokes.

**Motion.** A seven-second breath, slow enough to read as alive rather than as something blinking
for attention. The pointer interaction is the part worth explaining: a 0.75px stroke is not a hover
target, so instead of hit-testing 132 lines, each ray stores its own angle once and lights by how
close the pointer's angle is to it, with the shortest way round the circle so the seam at ±π does
not go dark. One `requestAnimationFrame` per move, and the whole thing returns early under
`prefers-reduced-motion`.

**Mobile.** Three real gaps, found by auditing rather than by looking: the landing's bar put four
links and a wordmark on one row, the dashboard's bar had no `flex-wrap` at all and would have pushed
its buttons off the edge, and every nav link was a 14px text target with no vertical padding. The
nav now scrolls sideways instead of hiding links or collapsing into a menu for four items; the
dashboard's two status lines drop to their own row; the KPI row goes to two columns rather than five
stacked cards; the submissions table keeps every column and scrolls rather than hiding data; and
targets get vertical padding under `@media (hover: none)`, so the desktop rhythm is untouched.

The widget got its own treatment, because it is the piece that lands on other people's phones: below
480px the popover stops being a floating panel and becomes a sheet pinned to the bottom edge, where
a thumb already is. Its inputs were already 44px tall at 16px type, which is what stops iOS zooming
the whole page on focus.

**GitHub in the header**, the way Expo carries theirs — mark, wordmark at display weight and
tracking, then the links, with the repository at the end and again in the footer.

## Stage 17 — attribution, illustrated cards, and a flake I had denied

**A test I had called deterministic was not.** Adding the FlyRank attribution turned the suite red
once, then green on a re-run, which is the worst possible signal and the reason I chased it instead
of shrugging. The cause was real: `pytest` runs in the same container as the live uvicorn process,
against the same database, and that process has a notification worker polling for due jobs every two
seconds. `claim_due` takes whatever is ready — including the job a test had just queued. So the
running server could deliver, successfully, the job a test had set up to watch fail, and the
assertion that it ends up `dead` would lose the race.

The fix has two halves. Test jobs are now queued an hour in the future, so nothing that polls for
*due* work can ever see them; and the tests drive their job by name through a new
`claim_one(submission_id)`, which mirrors `claim_due` for a single row. There is a new test asserting
that a second claim on the same row returns nothing, since "two workers must not both get it" is the
property the whole queue rests on. Fifty-one tests now, green five runs in a row and green again with
submissions in flight.

Worth being blunt about: `EVIDENCE.md` claimed determinism on the strength of three identical runs.
Three identical runs is evidence of nothing when the thing you are racing only wakes up every two
seconds.

**Illustrated cards.** The "how it works" section had three cards of prose. It now has four cards
that show the thing instead: the API call and its response, a browser window with the widget
rendering inside a page it does not own, the gauntlet a submission runs as a column of status codes,
and the worker log degrading and dead-lettering while the lead stays put. All four are drawn in HTML
and CSS rather than shipped as images — they stay crisp at any pixel density, weigh nothing, need no
build step, and follow the design tokens if the tokens change.

**Attribution.** FlyRank's wordmark sits in the footer, linked to the internship. It is self-hosted
rather than hotlinked: their asset should not be fetched from their servers on every page view, and
a link that rots would leave a broken image in our footer. Both files were read before being
committed — paths only, no script, no external references. It is also the one place a colour that is
not ours is allowed on the page, on the same principle Expo uses: somebody else's logo is content,
not chrome.

## Stage 18 — showing the dashboard, and three bugs

**A broken illustration, shipped.** The browser mock in the "Paste one line" card was `display:
flex` with no direction, so the chrome bar and the page sat *side by side* instead of stacked — a
black slab across the left half. It went out in Stage 17 and no test could have caught it, because
no test looks at CSS.

**I had said screenshots were impossible. They were not.** The claim rested on one failure back in
Stage 4, which is not enough to claim anything. Retrying properly: headless Chromium hangs in both
the new and the old mode after `CVDisplayLinkCreateWithCGDisplay failed`, and `screencapture` exits
1 because this terminal has no Screen Recording permission — but *headless* was the part that was
broken, not the browser. Running Brave visible with `--remote-debugging-port` and driving it over the
DevTools protocol works: navigate, put the key into `localStorage`, capture. Two attempts stood
between "impossible" and "twenty lines of Python", and I had stopped at the first one.

**What the first capture caught.** A real personal email address, in the submissions table, on its
way into a public repository. So the shot is taken against a throwaway tenant instead: a hundred and
forty-seven fabricated leads spread across a fortnight, plausible names, no real address anywhere,
deleted immediately afterwards. It also fixed a second problem — the honest dashboard had every
submission landing today, so the fourteen-day chart was twelve empty columns and two bars. A figure
should show the thing working, and that one showed it idle.

The key never appears on screen: it goes into `localStorage` through the protocol rather than being
typed into the form.

**Screenshot over drawing.** The HTML recreation that stood in for this is gone. It had one real
advantage — it could not go stale — and that is the cost now accepted: a redesign means retaking the
picture. The capture script lives outside the repository, so retaking it is a command, not an
afternoon. The video slot still works: drop `dashboard.mp4` into `app/static/brand/` and the page's
`HEAD` check plays it instead.

**And a fourth, spotted by the person looking at the page.** Above the screenshot sat a huge blurred
smear. Two mistakes stacked: the `<video>` element carried `poster="icon-16.png"` — a sixteen-pixel
icon stretched across a thousand — and it was visible at all because `hidden` is a `display: none`
from the browser's own stylesheet, which loses to any author rule, and mine said `.frame-body video
{ display: block }`. The attribute was there, doing nothing. Visibility is a class now, and the
poster is the screenshot, so a recording dropped in later opens on the right frame.

Both of those are the same lesson as the flex-direction bug earlier in this stage: I keep shipping
visual changes I have only read, in a project where I check everything else by running it.

**A 500 I introduced and then removed.** Allowlisting `dashboard.mp4` before the file existed meant
`read_bytes()` on a missing path — a `500` on a public route, in a system whose whole argument is
that it never returns one. Being on the allowlist and being on disk are two different facts. Both
asset routes go through one `immutable_asset()` helper now, and two tests cover it: an
allowlisted-but-absent file must be a clean 404, and the files that do exist must still serve with
their immutable cache. Fifty-three tests.

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
