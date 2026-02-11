# parcelLab — Returns Portal

## The situation

You're joining the returns team for a day. We run the customer-facing returns portals for a lot of brands you have heard of. Customers look up their order, see which items are eligible for return, and submit a request, you might have been in this situation yourself. The portal is live, but it's rough around the edges: the previous engineer left before finishing some critical backend work, tests are failing, and a few things are broken.

Below is the current backlog. The first three tasks (BR-001–003) are required; **you don't have to do everything else** — pick the electives that best show what you can do, and explain your choices in `DECISIONS.md`.

> Please do not fork this repository. Clone it without forking work locally, and submit as as personal repo on  Github, Gitlab, Codebergm ...   or just zip us a file.

## Getting started

**Stack:** Python 3.13+, Django, pytest, ruff, mypy. PyYAML is included if you want it for rules config.

```bash
uv sync

pytest              # you'll see some failures — that's intentional
python manage.py runserver
```

Open <http://localhost:8000/returns/> and try order `RMA-1001` with email `alex@example.com` or zip `10115`.

### Project layout

```
portal/
  data/orders_raw.json      # raw order payloads from upstream
  data/                     # your rules config goes here (you define the format)
  services/mapper.py        # maps raw payload → domain model (incomplete)
  services/eligibility.py   # return eligibility evaluator (stubbed)
  templates/returns/*       # Django + HTMX UI
  tests/*                   # pytest suite (some tests intentionally failing)
```

## Ground rules

> **Time limit: 4 hours.** If you hit the limit, stop and submit what you have. We'd rather see clean, well-reasoned partial work than a rushed complete solution.

**AI tools** are welcome. If you use them, keep a brief log in `AI_LOG.md` — we're curious how you use them, not whether you do.

## The backlog

**BR-001, BR-002, and BR-003 are required** — they're the core of the challenge and what every submission gets compared on. Everything else is an elective: pick one or two that play to your strengths, skip the rest, and tell us why in `DECISIONS.md`. Depth beats breadth.

---

### BR-001 · Complete the mapper gaps

Our upstream order system sends rich payloads, but the mapper was left unfinished — item-level flags never got wired up. The eligibility engine needs these to make decisions.

Missing fields on each article:
- `is_digital`
- `is_final_sale`
- `category`

Look at the raw data in `orders_raw.json` and the test fixtures to understand the different payload shapes you need to handle.

---

### BR-002 · Build the return eligibility engine

Right now, `evaluate_eligibility()` just marks everything as returnable. We need a real rules engine — one that's configurable, not hardcoded.

Design your own rules format (JSON, YAML, whatever you prefer) and implement the evaluator. It should return a clear result per item (returnable or not, reason, matched rule) and handle at least:
- Return window (delivered date + allowed days)
- Already fully returned
- Digital items
- Final-sale items

We intentionally don't provide a rules file — we want to see how you'd structure it.

---

### BR-003 · Fix and extend the test suite

Several tests are failing. Some depend on BR-001 and BR-002 being done, others may have their own issues. Make the suite green and add tests that give you confidence in your implementation.

---

### BR-004 · Category-specific return windows

Product just told us: different categories need different return windows. Electronics should be 14 days, apparel gets 30, and so on. If your rules engine is well-designed, this should be a natural extension — add per-category window config and make the evaluator respect it. Fall back to the order-level default when a category isn't configured.

---

### SEC-001 · Security audit

A security researcher has contacted us claiming they can access customer order data they shouldn't be able to. They want a fee to disclose the details. We'd rather understand our own exposure.

Audit the portal's **authentication and authorization model** — how a customer proves who they are, and how the app decides what they're allowed to see. We're not looking for a single planted bug; we want your assessment of the system.

Produce a short write-up (in `DECISIONS.md` or a `SECURITY.md`) that:

- **Lists the threats you found** — each with a one-line description of how it's exploited and what it exposes.
- **Ranks them by real-world exploitability** — not theoretical severity. A trivially scriptable attack against live customer data outranks one that needs a session you can't get.
- **Fixes the one you judge most important**, with a test that demonstrates the exploit before the fix and its absence after.
- **Says why you deprioritized the rest** — what you'd do with another day, and what you'd escalate to the team rather than fix solo.

We care more about how you reason about the exposure and where you choose to spend limited time than about the length of the list.

---

### FR-001 · Show returnable items only

Support keeps asking: can customers filter the articles list to only see what's actually returnable? Add a "Show returnable only" toggle using HTMX — no full page reload.

---

### FR-002 · Fix the return submission flow

The "Continue" button on the articles page is dead — the rest of the flow was apparently deleted before the last push. Build the missing pieces: article selection → confirmation → success. A customer should be able to complete a return end-to-end, and a submitted return must survive a server restart — persist it.

One thing support keeps seeing: impatient customers double-click submit, or hit refresh on the success page. What should happen then? Your call — just make it deliberate.

---

### OPEN-001 · Surprise us

See something that bugs you? Have an idea that would make the portal better? Go for it — just keep it scoped and tell us about it in `DECISIONS.md`.

---

## What to submit

- Working, type-safe code
- Small, readable commits
- `DECISIONS.md` — what you picked, what you skipped, and why
- `AI_LOG.md` — if you used AI tools

---

© parcelLab — May your returns always be smooth.
