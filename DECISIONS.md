# Decisions

## BR-001 · Mapper gaps

### `is_digital`
- **Decision:** Only trust the explicit `"digital"` boolean from the upstream payload. No fallbacks.
- **Rationale:** every available proxy signal is unreliable in at least one direction, so we only trust the field that actually means what we're asking:
  - `requires_shipping=False` is a *fulfillment* signal, not a product-type signal. A physically-mailed gift card or a store-pickup order can skip shipping without being digital.
  - **`category` / `product_type` describe merchandising, not delivery format.** A "digital" category routinely contains physical goods — a *digital camera*, a *digital piano*, a *digital watch*, boxed software on a DVD. All ship in a box and are all perfectly returnable. The converse also breaks: an e-book may be filed under `Books` next to hardcovers, and a gift-card code under `Gift Cards`, so a category match would miss genuinely digital items too.
  - Prefix matching (`product_type.startswith("Digital")`) compounds this — a `"Digital Accessories > Cables"` category is a false positive on the string alone.
- **Consequence:** the category derivation below and the `is_digital` derivation are deliberately **decoupled**. We parse `product_type` to populate `category`, but never feed `category` back into `is_digital`. Getting this wrong is asymmetric: falsely marking an item digital blocks a legitimate return and produces a support ticket, whereas the explicit flag simply reflects what upstream asserts.
- **Alternatives considered:** `requires_shipping=False` fallback, `product_type` prefix match, `category == "digital"` check. All rejected as unreliable.
- **If the flag is missing:** we default to `False` (returnable) rather than guessing. Upstream owns this fact; if it turns out payloads arrive without it, the right fix is to chase the missing field at the source, not to reverse-engineer it downstream.
- **Fixture gap:** The conftest EBOOK article lacked `digital=True`. Added it — the fixture represents a digital product, so the key should be present. The fixture was incomplete, not the design.

### `is_final_sale`
- **Decision:** Trust the explicit `"final_sale"` boolean when present; fall back to `"final-sale"` in the item's `tags` list.
- **Rationale:** Some upstream payloads use structured flags; others communicate the same information through tags. Both are intentional signals from the upstream system, so both are reliable.
- **Alternatives considered:** `product_type` or price-based heuristics — too indirect.

### `category`
- **Decision:** Use the `"category"` key directly when present. Fall back to the first segment of `"product_type"` (split on `" > "`, lowercased) when there is no `"category"` key.
- **Rationale:** `product_type` is a structured, explicit field following a `"TopLevel > Subcategory"` hierarchy. The first segment is a reliable category signal. This avoids coupling `is_digital` to `product_type` parsing while still enabling category derivation for both payload shapes.
- **Alternatives considered:** Using the full `product_type` string as-is — discarded because it's too granular for grouping.

---

## BR-002 · Return eligibility engine

Rules live in `portal/data/return_rules.yaml`; the evaluator is `portal/services/eligibility.py`.

### Deny-list model
- **Decision:** rules describe reasons to *block* a return. An article matching no rule is returnable.
- **Rationale:** `types.ArticleEligibility` documents `reason` and `matched_rule` as empty when returnable, so the existing contract already assumes only blocking rules carry an explanation. An allow-list would have to invent a "matched rule" for the happy path.

### Ordered rules, first match wins
- **Decision:** rules evaluate in file order; the first match blocks and supplies the reason. No `priority` field.
- **Rationale:** `ArticleEligibility.matched_rule` is singular, so exactly one rule must win. Making list order *be* the precedence keeps the answer to "why did the customer see this message?" visible in the file, rather than requiring a mental sort.
- **Ordering:** intrinsic properties (already returned → digital → final sale) come before the time-based window. An item that is final sale was never returnable at any point, so reporting "final sale" is more accurate than "the window closed", which implies the customer was merely too late. Visible on `RMA-1002`, where both items are past the window yet report their intrinsic reason instead.

### Closed condition vocabulary
- **Decision:** `condition` names a predicate registered in `_CONDITIONS`. Unknown names raise `RuleConfigError` at load time.
- **Rationale:** fails loudly on a config typo. The alternative — ignoring unrecognised rules — would silently make articles returnable, which is the expensive direction to get wrong.
- **Alternatives considered:** a mini expression language (`quantity_returned >= quantity`) would let the team add rules without code. Rejected: it needs a parser, or `eval` on a config file, which is a code-execution risk for a marginal gain. Worth revisiting if rule churn becomes frequent.

### Inclusive window, compared by date
- **Decision:** expired when `(today - delivered).days > window_days`, so a 30-day window is still open on day 30. Dates, not timestamps.
- **Rationale:** comparing timestamps means a window expires part-way through its final day, so the same "day 30" request succeeds in the morning and fails at night. Inclusive-by-date is what a customer reading "30 days" expects.

### Pydantic for config parsing
- **Decision:** parse the YAML into pydantic models.
- **Rationale:** `pyyaml` and `pydantic` are both already dependencies and `[tool.mypy]` already enables the `pydantic.mypy` plugin, so this is the path the scaffold points at. Under `strict = true`, `yaml.safe_load()` returns `Any`; pydantic converts that into typed config with useful validation errors, instead of hand-rolled `isinstance` checks.

### Config injection over cache-busting
- **Decision:** `evaluate_eligibility(order, rules=None)` — `None` uses the process-cached shipped file, tests pass an explicit `RulesConfig`.
- **Rationale:** existing callers (`views.py`, `api.py`) are unchanged, and rule tests do not depend on the shipped file's current contents or need `lru_cache.cache_clear()` between tests.

### Public surface, and config that validates too late
- **Decision:** `load_rules` is public alongside `RulesConfig`, `Rule` and `RuleConfigError`.
- **Rationale:** `evaluate_eligibility(order, rules=...)` is public and takes a `RulesConfig`, so a caller must have a supported way to *obtain* one from a file. Making the loader private would leave callers able to hand-build a config in Python but not read one from disk. The five names form one coherent surface.
- **Caveat:** today the only non-test caller is the internal `_default_rules()`, so this is partly speculative API. "Tests call it" would not on its own justify making it public.
- **Follow-up (not done):** the config is loaded *lazily*, on first evaluation, so a malformed `return_rules.yaml` surfaces as a 500 on the first customer request rather than at boot — the `RuleConfigError` validation fires too late to be operationally useful. The fix is small: a Django system check, or an `AppConfig.ready()` call to `load_rules()`, failing startup instead. Deliberately deferred as out of scope for BR-002, but it is the change that would turn the public loader into a genuinely used one.

### Known gap: undelivered orders
`mapper.map_order` falls back to `delivery_date = order_date` when an order has no fulfillments, so the return window starts counting **before the item ships**. `order_store._DELIVERY_AGE_DAYS` even labels `RMA-1003` as "just placed, not yet shipped". The domain model cannot currently distinguish "delivered today" from "never delivered", so a correct `not_yet_delivered` rule would require adding delivery state to `Order`. Left alone deliberately — it is a change to the shared domain type rather than to the rules engine, and the required scope did not call for it.

---

## Production readiness

If this shipped to production for 50 brands tomorrow, what breaks first?

- **JSON file as data store:** `orders_raw.json` is loaded on every request. Under any real load this needs a database or at least an in-process cache.
- **Authorization:** `get_order()` has no credential check. The session only records that *some* lookup was performed, not which order was verified. A customer who looks up their own order can fetch any other order's articles by guessing the order number. This is an IDOR and the highest-priority security issue.
- **No error handling on bad JSON:** if `orders_raw.json` is malformed the server 500s hard.

### Eligibility engine specifically

Roughly in the order I would expect them to hurt:

- **Refusal messages are English-only, and the customers are not.** `reason` strings are English literals in `return_rules.yaml`, rendered verbatim into the page. Both sample orders carry `order_locale: "de-DE"` with customers in Berlin and Munich, and `settings.LANGUAGE_CODE` is `en-us`. So a German customer is told "Final-sale items cannot be returned." today. `USE_I18N` is already `True`, so the machinery exists — but `gettext` extraction does not reach strings living in a YAML data file. The rule should carry a message *key* resolved against translation catalogues, or a locale-keyed map of reasons, with the order's locale threaded through to the evaluator. This is the one item on this list that is already wrong in production rather than merely fragile.

- **Rule changes apply retroactively.** Windows are read at evaluation time, not captured at purchase. Shortening apparel from 30 to 14 days instantly revokes the promise made to every customer who already bought — including orders delivered under the old terms. In the EU that is a consumer-rights problem, not just a UX one. Eligibility should be evaluated against the ruleset in force when the order was placed: snapshot the relevant terms onto the order, or effective-date rulesets and select by `order_date`. The `version` field is parsed but currently unused; it is the obvious hook.

- **Nothing enforces statutory minimums.** The config will happily accept `apparel: 3`, and the evaluator will enforce it. EU distance selling grants a 14-day withdrawal right, so a misconfigured category can silently put a brand in breach. `load_rules` should reject windows below a jurisdictional floor. Related, and worth a lawyer rather than an engineer: the blanket `digital-item` rule is probably too broad for the EU, where the withdrawal right on digital goods is waived by *starting the download* with consent, not by the item being digital.

- **Timezone is inconsistent with Django's own configuration.** Django is timezone-aware (`USE_TZ = True`, `TIME_ZONE = "UTC"`), but `mapper._parse_dt` strips tzinfo and `_window_expired` calls `date.today()`, which reads the *server's* local date rather than the configured zone. On a host that is not UTC these disagree, so the window can close a day early or late. Fix is small — `django.utils.timezone.localdate()` — but the deeper question is whose midnight should count: the server's, the brand's, or the customer's.

- **One global config, loaded once per process.** `_RULES_PATH` is a single module-level file and `_default_rules` is `lru_cache(maxsize=1)`, so rules are per-deployment and read once at first use. Fifty brands need fifty rulesets keyed by tenant, and a cache that can be invalidated without a rolling restart.

- **No self-serve configuration.** Changing a window is a pull request and a deploy, so the returns team has to queue behind engineering for what is really a business setting. A database-backed ruleset with an admin UI fixes that, but it gives up what the file currently provides for free: version control, code review, and atomic rollback. Whatever replaces it needs an audit trail of who changed what, and a dry-run that replays a candidate ruleset against recent orders so a bad edit is caught before it silently blocks every return. Note the tension with the closed condition vocabulary — a UI can only expose conditions that already exist in code, so genuinely new rule *types* still require a deploy.

- **No observability.** Nothing records which rule fired. When returns drop after a config change, there is no way to attribute it. `matched_rule` is already computed and discarded outside the response — emitting it as a counter is nearly free and would make config changes measurable.
