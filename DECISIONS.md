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

## Production readiness

If this shipped to production for 50 brands tomorrow, what breaks first?

- **JSON file as data store:** `orders_raw.json` is loaded on every request. Under any real load this needs a database or at least an in-process cache.
- **Authorization:** `get_order()` has no credential check. The session only records that *some* lookup was performed, not which order was verified. A customer who looks up their own order can fetch any other order's articles by guessing the order number. This is an IDOR and the highest-priority security issue.
- **Rules hardcoded/file-based:** a YAML file works for a single deployment, but 50 brands means 50 different rule sets — the rules need to be per-brand and stored in a database with an admin UI.
- **No error handling on bad JSON:** if `orders_raw.json` is malformed the server 500s hard.
