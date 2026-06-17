# FitFindr

AI agent that searches mock secondhand listings, suggests outfits based on your wardrobe, and generates shareable fit card captions.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set your Groq API key in `.env`:
```
GROQ_API_KEY=your_key_here
```

Run the app:
```bash
python app.py
```

Run tests:
```bash
pytest tests/
```

---

## Tool Inventory

### `search_listings(description: str, size: str | None = None, max_price: float | None = None) -> list[dict]`

**Purpose:** Search mock listings from `data/listings.json` by keywords, optional size, and optional price ceiling.

**Returns:** List of matching listing dicts sorted by relevance. Each dict has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`. Empty list if no matches.

### `suggest_outfit(new_item: dict, wardrobe: dict) -> str`

**Purpose:** Suggest 1–2 outfits combining the thrift find with the user's wardrobe (or general advice if wardrobe is empty). Uses Groq LLM.

**Returns:** Non-empty string with outfit suggestions.

### `create_fit_card(outfit: str, new_item: dict) -> str`

**Purpose:** Generate a casual 2–4 sentence social media caption for the outfit. Uses Groq LLM with higher temperature.

**Returns:** Fit card caption string, or error message string if outfit input is empty.

---

## Planning Loop

1. LLM parses the user query into `description`, `size`, `max_price`
2. `search_listings` runs — if empty, set error and **stop** (do not call suggest)
3. Top result → `selected_item`
4. `suggest_outfit(selected_item, wardrobe)` → outfit text
5. `create_fit_card(outfit, selected_item)` → fit card
6. Return session to UI

The agent branches on search results — it does not call all three tools unconditionally.

---

## State Management

A `session` dict tracks: `query`, `parsed`, `search_results`, `selected_item`, `wardrobe`, `outfit_suggestion`, `fit_card`, `error`. The same `selected_item` dict passes from search → suggest → fit card without re-prompting.

---

## Interaction Walkthrough

**User query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1 — Tool called:**
- Tool: `search_listings`
- Input: `description="vintage graphic tee"`, `size=None`, `max_price=30.0`
- Why: User wants a specific item type with a price cap
- Output: 3 listings; top match is **Y2K Baby Tee — Butterfly Print** ($18, Depop, excellent). All three graphic/vintage tees under $30 are returned.

**Step 2 — Tool called:**
- Tool: `suggest_outfit`
- Input: `new_item=<top tee listing>`, `wardrobe=get_example_wardrobe()`
- Why: User asked how to style it with their existing clothes
- Output: Outfit string naming wardrobe pieces (e.g. baggy jeans + combat boots)

**Step 3 — Tool called:**
- Tool: `create_fit_card`
- Input: `outfit=<step 2 string>`, `new_item=<top tee listing>`
- Why: Generate a shareable caption
- Output: Casual fit card mentioning item, price, and platform

**Final output to user:** Three UI panels — listing details, outfit idea, fit card caption.

---

## Error Handling and Fail Points

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| `search_listings` | No results (e.g. `"designer ballgown"`, size `"XXS"`, max_price `5`) | `"No listings matched your search… Try broadening your keywords, size, or budget."` Stops before suggest. |
| `suggest_outfit` | Empty wardrobe | Returns general styling advice — **not** an error. Continues to fit card. |
| `create_fit_card` | Empty outfit string | Returns `"Couldn't create a fit card — outfit suggestion was missing or incomplete."` Agent stops. |

**Tested example:** `search_listings("designer ballgown", size="XXS", max_price=5)` returns `[]`. Full agent run sets `session["error"]` and leaves `fit_card` as `None`.

---

## Spec Reflection

**One way planning.md helped during implementation:**

Writing the planning loop as explicit if/else branches (empty search → stop, empty outfit → stop) made it clear where to branch in `run_agent()` before writing code. The architecture diagram also made it obvious that `selected_item` had to be the exact dict passed into both downstream tools.

**One divergence from your spec, and why:**

The course example mentions 3 results with `size="M"`, but our dataset only has one true vintage graphic tee in size M/S/M under $30 (Y2K Baby Tee). Without a size filter, 3 relevant tees are returned with the band tee ranked first. This matches real search behavior better than forcing 3 results when the size filter legitimately narrows matches.

---

## AI Usage

**Instance — `search_listings` implementation:**
Gave Claude the Tool 1 spec block from planning.md (inputs, return fields, failure mode) and asked it to implement using `load_listings()`. Verified generated code filtered by price and size, scored keywords, and returned `[]` instead of raising. Tested with 3 queries before accepting.





