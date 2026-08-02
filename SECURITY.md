# SEC-001 · Security audit

Scope: the portal's **authentication and authorization model** — how a customer proves who they are, and how the app decides what they may see. Findings are ranked by *real-world exploitability*, not by theoretical severity.

## How the model works today

A customer supplies an order number plus **either** the email address **or** the zip code on the order (`LookupForm` → `order_store.find_order`). On a match, the order number is written into the session:

```python
request.session["order_number"] = order.order_number
```

From that point the session value **is** the authorization token. Two places consume it, and before this audit they disagreed:

| Consumer | Check | Correct? |
|---|---|---|
| `views.py:36` (browser) | `session["order_number"] != order_number` → redirect | yes |
| `api.py:104` (API) | `not session.get("order_number")` → 403 | **no** |

There are no user accounts, no passwords, and no `django.contrib.auth` login anywhere. Authorization is left to each individual view rather than enforced centrally — which is the structural reason the two drifted apart.

---

## Findings

### 1 · Any customer could read any order via the API — **fixed in this change**

**Exploit.** Look up an order you legitimately own, then request any other order number from `GET /api/returns/{order_number}/articles/`. `api.py:104` verified only that *some* order number sat in the session, never that it matched the order being requested.

**Exposes.** Recipient name, email address, full street address, city, zip, order and delivery dates, and every line item with prices — for any order in the system.

**Exploitability: highest.** Deterministic — one request per victim, no guessing. Order numbers are sequential (`RMA-1001`, `RMA-1002`, …), so the entire store is enumerable in a single pass. The only prerequisite is one legitimate order, which costs an attacker one small purchase. Reproduced before the fix:

```
lookup own order (RMA-1001) : 200
GET RMA-1002/articles       : 200
  LEAKED -> Lee Schmidt | lee@example.com | Rosental 45, c/o Office 80331 Munich
  items  -> [('SHOES-CLR-42', 49.99), ('JACKET-GRN-L', 89.99)]
```

The browser flow was never affected — `ArticlesView` always compared the two values. The API was the outlier.

### 2 · Zip code as a credential, unthrottled, against enumerable order numbers

**Exploit.** Loop order numbers against candidate zips at `POST /api/returns/lookup/` (or `POST /returns/`). No throttling exists — `REST_FRAMEWORK` in `settings.py` sets only `DEFAULT_SCHEMA_CLASS`, with no `DEFAULT_THROTTLE_CLASSES`, no lockout and no CAPTCHA.

**Exposes.** The same data as finding 1, but requiring **no prior access at all**.

**Exploitability: high.** Fully scriptable by an unauthenticated attacker. German postal codes have roughly 8,000 valid values, and sequential order numbers shrink the search space further. Slower per record than finding 1, but it needs nothing to start.

**This is the more fundamental flaw, and fixing finding 1 does not touch it.** A five-digit postcode shared by an entire neighbourhood is not a secret; it is at best a weak second factor.

### 3 · No CSRF enforcement on the DRF lookup endpoint

**Exploit.** A cross-site auto-submitting form posts to `/api/returns/lookup/` and rewrites the victim's `session["order_number"]`. DRF's `SessionAuthentication.enforce_csrf()` only runs once `request.user` is an authenticated Django user; this app never calls `login()`, so `request.user` is always `AnonymousUser` and the check never fires. The Django view does render `{% csrf_token %}`.

**Exposes.** Nothing the attacker does not already hold — the lookup only succeeds with a valid order number and identifier, which the attacker must supply. Worst case is pinning a victim's session to an order the attacker already knows.

**Exploitability: low impact despite being easy.** A real inconsistency between the two surfaces, but it yields no data.

### 4 · Session key not rotated on successful lookup

**Exploit.** Classic session fixation: plant a known session ID in the victim's browser, wait for them to authenticate, reuse the ID. Neither `LookupView.post` nor `ReturnsViewSet.lookup` calls `cycle_key()`.

**Exposes.** Full access to whichever order the victim looked up.

**Exploitability: low.** Requires a pre-planted session ID via a subdomain, MITM, or a separate bug. The application provides no vector to plant one, so this is not independently exploitable here.

### 5 · Session cookie flags left at Django defaults

`SESSION_COOKIE_SECURE` and `CSRF_COOKIE_SECURE` are unset, so both default to `False`; `SESSION_COOKIE_SAMESITE` is likewise unset. `HttpOnly` is `True` by default and is fine.

**Exploitability: deployment-dependent.** The session cookie is the entire authorization token for an order, so served without enforced TLS it is interceptable in transit. Only bites if deployed without a proxy that sets these flags.

### 6 · `DEBUG = True` and a hardcoded `SECRET_KEY`

`settings.py:17,20` — `SECRET_KEY = "dev-secret-key"` and `DEBUG = True`, both already carrying "unsuitable for production" comments.

**Exploitability: not a live application flaw.** If ever deployed unchanged, tracebacks would leak source and local variables, and a known signing key would allow forging CSRF tokens and signed values. Sessions are database-backed and referenced by ID rather than signed into the cookie, so the blast radius is narrower than full session forgery. Listed for completeness; this is deployment hygiene the team already flagged.

---

## Considered and ruled out

- **Timing side channel in `find_order`'s linear scan** — three orders in the fixture; any signal is noise.
- **XSS in templates** — no `|safe`, `mark_safe`, or `autoescape off` anywhere in `portal/`; Django's auto-escaping is intact at every interpolation.
- **Public `/api/schema/`, `/api/docs/`, `/api/redoc/`** — exposes nothing beyond what the router already serves.
- **`BasicAuthentication` via DRF defaults** — dead path; there are no user accounts to authenticate against.
- **`ALLOWED_HOSTS`** — correctly restrictive for the current config.

Two things the code already gets right and should stay that way: the lookup error message does not distinguish "unknown order" from "wrong identifier", and `ArticlesView` binds the session to the requested order.

---

## The fix

One line in `api.py`, mirroring the check `ArticlesView` already performed:

```python
-if not request.session.get("order_number"):
+if request.session.get("order_number") != order_number:
```

**Ordering matters.** The check runs *before* `get_order()`, so a caller cannot distinguish "this order exists but is not yours" (previously 403) from "no such order" (previously 404). Both now return 403, removing an order-number enumeration oracle that the naive fix would have left behind. The 404 branch survives only for the case where the caller's own order disappears from the store between lookup and request.

**Tests** — `portal/tests/test_api.py::TestCrossOrderAccess`, four cases: the cross-order read is refused; no PII from the other order appears in the body; the legitimate path still works; unknown and someone-else's orders are indistinguishable.

Demonstrated before and after rather than asserted. Against the unfixed code, three of the four fail:

```
FAILED test_cannot_read_another_customers_order
FAILED test_does_not_leak_another_customers_personal_data
FAILED test_unknown_order_is_indistinguishable_from_someone_elses
3 failed, 1 passed
```

After the fix, all four pass, and the full suite is green at 118.

One existing test changed as a direct consequence: `test_articles_for_unknown_order_returns_404` now expects 403. That is the anti-enumeration property, not a regression, and the renamed test documents it.

---

## Why the rest was deprioritized

**Finding 2 is the one I would fix next, and it is bigger than a patch.** Two separable pieces:

- *Rate limiting* is the cheap half — a DRF throttle class on the lookup endpoint. I deliberately left it out. Per-process `LocMemCache` throttling is close to theatre behind multiple workers, so doing it properly means choosing a shared cache backend, which is an infrastructure decision rather than a code one. Adding five lines here would have looked like a fix while barely being one.
- *Retiring zip as a credential* is a *product* decision, not an engineering one. It exists because customers lose order confirmation emails, and removing it will increase support load. That trade belongs to whoever owns the returns funnel. My recommendation would be to keep zip for the low-risk read path but require the email for anything that mutates state, and to make order numbers non-sequential so enumeration stops being free.

**Findings 3 and 4** are genuine but yield nothing on their own — 3 hands the attacker only data they already had, and 4 needs a session-planting vector this app does not provide. Both are cheap (`cycle_key()` on successful lookup; an explicit authentication class on the viewset) and belong in a follow-up, not ahead of finding 2.

**Findings 5 and 6** are deployment configuration. They matter enormously in production and not at all in this repository, and they are the kind of thing that belongs in a deployment checklist rather than in application code.

### With another day

1. Rate limiting on `lookup`, backed by a shared cache, plus alerting on failed-lookup rate — the detection gap is arguably worse than the control gap, since nothing today would reveal that a scrape was happening.
2. Centralize authorization. The root cause of finding 1 was not a typo; it was that each view re-implements the check and one of them got it wrong. A single helper — or a DRF permission class — that resolves "which order is this session entitled to?" would make the class of bug structurally hard to reintroduce. `get_order()` performing no authorization while being freely callable is the same footgun waiting for the next endpoint.
3. `cycle_key()` on lookup, an explicit authentication class on the viewset, and the cookie flags.

### What I would escalate rather than fix alone

- **Retiring or downgrading zip-as-credential** — product and support impact, not my call.
- **Non-sequential order numbers** — touches upstream systems, fulfilment, and customer service scripts.
- **Whether this exposure was already exploited.** The researcher's claim in the brief is credible: finding 1 is exactly what someone poking at the API would trip over first. Nothing in the app logs authorization failures or successful cross-order reads, so the honest answer is that we cannot currently tell from the application side. That question — and any breach-notification obligation that follows, which under GDPR is a 72-hour clock — goes to the team immediately, not into a pull request.
