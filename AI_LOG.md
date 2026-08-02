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
