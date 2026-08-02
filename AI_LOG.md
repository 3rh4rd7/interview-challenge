# AI Log

## Tool
Claude Code (Anthropic CLI)

---

## BR-001 · Mapper gaps (2026-08-02)

### What I asked Claude to do
- Analyze the repository and produce an implementation plan for the engineering challenge.
- Run the project locally so I can play with the UI.
- Then plan BR-001 specifically before touching any code.
- Then implement BR-001, add missing tests, and document decisions.

### How the interaction shaped the implementation

**`is_digital` logic:** Claude initially proposed three fallback signals: explicit `"digital"` key, `requires_shipping=False`, and `product_type` prefix match. I pushed back on `requires_shipping` — it's a fulfillment flag, not a product-type signal. Claude agreed and dropped it. Then I pushed back on `product_type.startswith("Digital")` — it's fragile against hypothetical category names like `"Digital Accessories"`. We discussed whether the first segment exact-match (`"digital"`) would be safer; I decided to drop the `product_type` fallback for `is_digital` entirely and just trust the explicit boolean. Claude flagged that the conftest EBOOK fixture was missing `digital=True` and that it was a fixture gap, not a design question — I agreed.

**`is_final_sale` logic:** Claude proposed explicit `"final_sale"` key with `"final-sale"` tag fallback. I accepted this without pushback — it matches the data we have in both payload shapes.

**`category` logic:** Claude proposed explicit `"category"` key with `product_type` first-segment fallback (lowercased). I accepted this — `product_type` is a structured, explicit hierarchy and the first segment is a reliable top-level grouping.

### Net result
All decisions reflect deliberate back-and-forth. Claude wrote the code; I directed the design choices.

### Naming
Asked whether `_category` should be `_get_category`, on the assumption that functions should be verbs. Claude pushed back: `get_` is a Java/C# convention that Python leans away from (hence `@property`), and PEP 8 mandates casing but not verbs — the stdlib is full of noun-named functions (`os.path.dirname`, `inspect.signature`, `dataclasses.fields`). It suggested `_derive_category` instead, on the grounds that the function is not a plain accessor but runs a fallback chain. Adopted.

---

## BR-002 · Eligibility engine (2026-08-02)

### Approach
Asked for requirements analysis and an execution plan *before* any code, then reviewed the plan and approved it.

### What the analysis surfaced
Reading the existing contract first changed the design. `types.ArticleEligibility` documents `reason` and `matched_rule` as empty when returnable, which implies a deny-list rather than an allow-list, and `matched_rule` being singular forces a first-match-wins model. `articles.html` renders `reason` directly, so reasons are customer-facing copy rather than internal codes. Claude also noticed `pydantic` was already a dependency *and* that `[tool.mypy]` already enables the `pydantic.mypy` plugin — a strong hint from the scaffold about the intended tool for config parsing.

It also flagged that `portal/models.py` defines `EligibilityResult` / `ReturnRegistration` / `LineItem` which nothing imports, and recommended leaving them alone rather than half-migrating to a second result shape.

### Decisions I was asked to make
Claude presented three choices with recommendations rather than picking silently:
1. **Rule precedence** — intrinsic properties before the time window, so a final-sale item says "final sale" rather than "window closed".
2. **Inclusive window boundary**, compared by date not timestamp, to avoid a window expiring mid-day.
3. **Build the category-window resolver in BR-002**, leaving BR-004 as a data-only change.

I approved all three.

### Review round
Two things I raised on reading the result:

**`load_rules` was hard to read.** It did four jobs in one body and repeated the same `f"Rules file at {path}"` prefix five times, so the actual flow was buried in error handling. Claude split it into `_read_yaml_mapping`, `_build_config` and `_reject_unknown_conditions`, leaving `load_rules` as four lines that read as a summary — and noted this also matches how `mapper.py` is structured.

**Why is `load_rules` public?** Claude's answer was that it completes the injection API: `evaluate_eligibility(order, rules=...)` is public and takes a `RulesConfig`, so callers need a supported way to load one from disk. It also conceded the honest counterpoint — the only non-test caller today is internal, so the API is partly speculative, and "tests call it" would not justify it alone. Kept public; the reasoning and the deferred startup-validation follow-up are recorded in `DECISIONS.md`.

### Production readiness
I prompted for the production concerns specific to the eligibility engine, having spotted two myself: the reason strings are not translatable, and the rules cannot be configured without a deploy. Claude grounded both in the actual data rather than leaving them abstract — both sample orders are `order_locale: "de-DE"` while `settings.LANGUAGE_CODE` is `en-us`, so German customers are shown English refusals today.

It also found one I had not: `settings.USE_TZ` is `True` with `TIME_ZONE = "UTC"`, but `mapper._parse_dt` strips tzinfo and my window check calls `date.today()`, which reads the *server's* local date instead of Django's configured zone. On a non-UTC host the window closes a day early or late. And it raised retroactive rule changes — shortening a window instantly revokes a promise already made to customers who bought under the old terms — which is the concern I would now rank above both of mine.

### Verification
57 tests passing, `ruff check` clean, `mypy --strict` clean. Beyond the unit tests, the engine was run against the real `orders_raw.json` data to confirm the precedence ordering behaves as intended on `RMA-1002`, where both articles are past the window but correctly report their intrinsic reason instead.

---

## BR-003 · Test suite (2026-08-02)

### Approach
Again asked for a gap analysis and a plan before any code.

### What the analysis found
Two findings I would not have reached quickly on my own:

- **`order_store.py` had zero tests**, despite containing `find_order` — the function that decides whether a customer's identifier matches an order. The portal's credential check was covered only incidentally, through view tests.
- **The production payload shape was untested.** `orders_raw.json` uses explicit `category`/`digital`/`final_sale` keys while the conftest fixtures use `product_type`/`tags`, and every mapper unit test ran on fixtures. So the branches real data hits had no direct coverage — `is_digital` only by accident, via a fixture we had edited during BR-001.

It also spotted that `raw_order_1003` was defined in conftest and never referenced — a dead fixture describing exactly the untested no-fulfillments case.

### Scope discipline
Claude declined to write the cross-order test against `api.py`, pointing out it would *fail* — the API checks only that some order is in session, not that it matches the requested one — and that adding a red test would contradict BR-003's "make the suite green", while the exploit-then-fix demonstration is what SEC-001 explicitly asks for. It added the equivalent test against `views.py`, which passes, as a regression guard. I agreed with the split.

### Verifying the tests actually bite
Unprompted, Claude mutation-checked its own work: it disabled the identifier comparison in `find_order`, confirmed exactly the three negative-path tests failed, then restored the file and re-ran the suite. Worth recording because a credential test that still passes against broken auth is worse than no test at all.

### Result
32 passing / 4 failing at the start of the challenge, **98 passing** now. `ruff check` and `mypy --strict` clean.

---

## BR-004 · Category-specific return windows (2026-08-02)

### Approach
Plan first again. Because the resolver already existed from BR-002, the config change was three lines — so the analysis was worth more than the implementation here.

### What the analysis surfaced
Claude's main finding was that BR-004 does not just add config, it changes what `category` *is*: previously inert data, now a dictionary lookup key. That introduces three silent failure modes — upstream casing mismatches, hand-typed config keys, and typos — all of which quietly apply the default window instead of erroring. It also noted these cannot be validated the way unknown rule conditions are, because the category universe comes from upstream rather than from us.

It had already spotted that `_derive_category` lowercased the `product_type` branch but returned the explicit `category` key untouched, so the existing code only worked because `orders_raw.json` happens to be lowercase.

### A test that earned its place
I chose to normalise in the mapper. A test then failed because it built an `Article` directly, bypassing the mapper. Rather than quietly rewriting the test to route through `map_order`, Claude flagged that the failure was evidence: the "category is canonical" invariant is convention only, nothing in the type system enforces it, and every eligibility fixture constructs articles by hand. It added normalisation to the lookup as well and explained why, instead of treating the red test as noise.

### Restraint I asked for indirectly
Claude declined to invent return windows for categories beyond the two the brief named, on the grounds that guessing return policy for an unfamiliar business is worse than leaving them on the default. It also declined to add an EU statutory minimum, correctly treating it as a legal question rather than an engineering one, and left it in the production-readiness notes where it was already recorded.

### Verification
114 tests passing, `ruff check` and `mypy --strict` clean. Also exercised end to end at 20 days post-delivery: electronics expired on its 14-day window while apparel and unconfigured footwear both survived on 30, and a deliberately mis-cased `ELECTRONICS` article resolved correctly.

---

## SEC-001 · Security audit (2026-08-02)

### Approach
Claude had already spotted the cross-order read in `api.py` back in the very first repository analysis, and deliberately left it unfixed through BR-003 so the exploit-before/fix-after demonstration would belong to this task.

For the audit itself it ran a second, independent pass over everything *else* — explicitly instructed to skip the finding we already had — covering the credential model, enumeration, rate limiting, session handling, CSRF, Django settings, templates and the DRF surface. I liked that the two passes were kept separate: the known bug did not anchor the search for the unknown ones.

### What each pass contributed
Mine/Claude's direct analysis produced the IDOR, a working reproduction against real data, and confirmation that the browser flow was unaffected. The second pass produced the unthrottled zip-code credential, the DRF CSRF gap (with the specific mechanism — `SessionAuthentication.enforce_csrf` never fires because `request.user` is always `AnonymousUser`), missing session rotation, cookie flags, and `DEBUG`/`SECRET_KEY`. It also ruled several candidates *out* with reasons, including verifying there is no `|safe`/`mark_safe` anywhere, which is as useful as the findings themselves.

### Judgement calls worth recording
- **Ranking.** Claude ranked the IDOR above the brute-force front door, but said plainly the ordering was arguable and that the credential model is the more fundamental flaw which the fix does not address. I would rather see the uncertainty stated than a confident false ordering.
- **Anti-enumeration.** It noticed the naive fix would leave an oracle — 403 for "exists but not yours" versus 404 for "no such order" — and placed the authorization check before the existence lookup so both return 403. That deliberately broke one of its own BR-003 tests, and it updated that test with a docstring explaining the change rather than quietly editing the expectation.
- **Declining scope.** I told it not to add DRF throttling. It had already argued against doing so, on the grounds that per-process throttling behind multiple workers would look like a fix without being one — which is a better reason than "out of scope".

### A mistake
While adding the exploit tests it made a bad edit that renamed an unrelated existing test by appending an underscore. It caught this immediately, reverted it, and verified the file was byte-identical to `HEAD` before continuing rather than assuming.

### Verification
118 tests passing, `ruff check` and `mypy --strict` clean. The exploit was reproduced against real data before the fix and re-run after; three of the four new tests fail against the unfixed code. `portal/api.py` has a pre-existing formatting deviation at line 146 that was left untouched to keep the security diff to a single line plus its comment.
