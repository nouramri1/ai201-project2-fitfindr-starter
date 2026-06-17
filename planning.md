# FitFindr — planning.md

> Complete this document before writing any implementation code.

---

## Tools

### Tool 1: search_listings

**What it does:**
Searches the mock listing database (`data/listings.json`) via `load_listings()` and returns items matching keyword description, optional size, and optional max price. Returns an empty list when nothing matches — never raises an exception.

**Input parameters:**
- `description` (str): Keywords describing what the user wants (e.g. `"vintage graphic tee"`)
- `size` (str | None): Optional size filter; case-insensitive substring match (e.g. `"M"` matches `"S/M"`)
- `max_price` (float | None): Optional maximum price in dollars (inclusive)

**What it returns:**
A `list[dict]` of matching listing dicts, sorted by relevance (best match first). Each dict contains: `id`, `title`, `description`, `category`, `style_tags` (list[str]), `size`, `condition`, `price` (float), `colors` (list[str]), `brand` (str | None), `platform` (str). Returns `[]` if no matches.

**What happens if it fails or returns nothing:**
The tool returns an empty list `[]`. The agent sets `session["error"]` with a helpful message (e.g. "No listings matched… Try broadening your keywords, size, or budget.") and returns early — it does **not** call `suggest_outfit`.

---

### Tool 2: suggest_outfit

**What it does:**
Given a thrifted listing and the user's wardrobe, calls Groq (`llama-3.3-70b-versatile`) to suggest 1–2 complete outfits. Names specific wardrobe pieces when available; gives general styling advice when the wardrobe is empty.

**Input parameters:**
- `new_item` (dict): A listing dict from `search_listings` (same fields as in `listings.json`)
- `wardrobe` (dict): Wardrobe object with an `items` key — list of wardrobe item dicts from `wardrobe_schema.json` (`name`, `category`, `colors`, `style_tags`, `notes`)

**What it returns:**
A non-empty `str` with 1–2 outfit suggestions written in plain language.

**What happens if it fails or returns nothing:**
- **Empty wardrobe (`items == []`):** Not a failure. Returns general styling advice for the new item. Agent continues to `create_fit_card`.
- **LLM failure or empty string:** Agent sets `session["error"] = "Couldn't generate outfit suggestions right now. Please try again."` and returns early.

---

### Tool 3: create_fit_card

**What it does:**
Takes the outfit suggestion string and listing details, calls Groq with higher temperature (0.9) to generate a casual 2–4 sentence Instagram/TikTok caption mentioning item name, price, and platform naturally.

**Input parameters:**
- `outfit` (str): The outfit suggestion string from `suggest_outfit`
- `new_item` (dict): The listing dict for the thrifted item

**What it returns:**
A `str` — either a shareable fit card caption, or a descriptive error message if input is invalid.

**What happens if it fails or returns nothing:**
- **Empty/whitespace `outfit`:** Tool returns `"Couldn't create a fit card — outfit suggestion was missing or incomplete."` Agent sets `session["error"]` to that message and stops.
- **LLM failure:** Tool returns `"Couldn't generate a fit card right now. Please try again."` Agent sets `session["error"]` and stops.

---

## Planning Loop

**How does your agent decide which tool to call next?**

1. **Initialize** session with `_new_session(query, wardrobe)`.
2. **Parse query** using Groq LLM — extract `description`, `size`, `max_price` as JSON → store in `session["parsed"]`. If parsing fails, set error and return.
3. **Call `search_listings`** with parsed params → `session["search_results"]`.
   - **If `search_results` is empty:** set `session["error"]` to a specific message telling the user what failed and to try broadening keywords/size/budget. **Return early. Do not call `suggest_outfit`.**
   - **If results exist:** set `session["selected_item"] = search_results[0]` (top match).
4. **Call `suggest_outfit(selected_item, wardrobe)`** → `session["outfit_suggestion"]`.
   - If empty string: set error, return early.
5. **Call `create_fit_card(outfit_suggestion, selected_item)`** → `session["fit_card"]`.
   - If result starts with `"Couldn't"`: set error, return early.
6. **Return session** — interaction complete.

The agent is **done** when `fit_card` is set or when an error causes early return. It never calls all three tools unconditionally.

---

## State Management

**How does information from one tool get passed to the next?**

All data lives in a single `session` dict for each user interaction:

| Field | Set by | Used by |
|-------|--------|---------|
| `query` | init | reference |
| `parsed` | LLM parse | `search_listings` inputs |
| `search_results` | `search_listings` | selecting top item |
| `selected_item` | planning loop | `suggest_outfit`, `create_fit_card` |
| `wardrobe` | init (from UI choice) | `suggest_outfit` |
| `outfit_suggestion` | `suggest_outfit` | `create_fit_card` |
| `fit_card` | `create_fit_card` | UI output |
| `error` | any failure branch | UI error display |

The same `selected_item` dict flows unchanged from search → suggest → fit card. The same `outfit_suggestion` string flows from suggest → fit card. No re-prompting or hardcoded values between steps.

---

## Error Handling

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| `search_listings` | No results match the query | Sets `session["error"]` to: "No listings matched your search for '{description}'… Try broadening your keywords, size, or budget." Returns early; `outfit_suggestion` and `fit_card` stay `None`. |
| `suggest_outfit` | Wardrobe is empty | **Not an error.** Returns general styling advice. Agent continues to `create_fit_card`. |
| `suggest_outfit` | LLM returns empty string | Sets `session["error"]` to "Couldn't generate outfit suggestions right now. Please try again." Returns early. |
| `create_fit_card` | Outfit input is missing or incomplete | Tool returns error string. Agent sets `session["error"]` to that message. Returns early. |

---

## Architecture

```
User query
    │
    ▼
Planning Loop ───────────────────────────────────────────┐
    │                                                    │
    ├─► LLM parse query → session["parsed"]              │
    │       │ parse fails                                │
    │       └──► [ERROR] "Couldn't understand…" → return │
    │                                                    │
    ├─► search_listings(description, size, max_price)    │
    │       │ results=[]                                 │
    │       ├──► [ERROR] "No listings matched…" → return │
    │       │                                            │
    │       │ results=[item, ...]                        │
    │       ▼                                            │
    │   Session: selected_item = results[0]              │
    │       │                                            │
    ├─► suggest_outfit(selected_item, wardrobe)          │
    │       │ empty string                               │
    │       └──► [ERROR] outfit failed → return          │
    │       │                                            │
    │   Session: outfit_suggestion = "..."               │
    │       │                                            │
    └─► create_fit_card(outfit_suggestion, selected_item)│
            │ error string                               │
            └──► [ERROR] fit card failed → return        │
            │                                            │
        Session: fit_card = "..."                        │
            │                                            └─ error paths return here
            ▼
        Return session → app.py → 3 UI panels
            ↕
      Session / State dict
```

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

For `search_listings`, I'll give Claude the Tool 1 block from planning.md (inputs, return value, failure mode) and ask it to implement the function using `load_listings()` from `utils/data_loader.py`. Before running, I'll verify it filters by all three parameters, scores by keyword + phrase overlap, and returns `[]` on no match. I'll test with: `"vintage graphic tee"` + `max_price=30`, `"designer ballgown"` + `size="XXS"` + `max_price=5`, and `"jacket"` + `max_price=10`.

For `suggest_outfit` and `create_fit_card`, I'll give Claude each tool's spec block and ask for Groq LLM integration with empty-wardrobe handling and empty-outfit guard. I'll verify outputs are non-empty strings and that `create_fit_card("", item)` returns an error message not an exception.

**Milestone 4 — Planning loop and state management:**

I'll share the Architecture diagram and Planning Loop + State Management sections with Claude and ask it to implement `run_agent()` in `agent.py` and `handle_query()` in `app.py`. Before running, I'll check: does it branch on empty search results? Does it store values in session? Does it skip `suggest_outfit` when search returns nothing? I'll test with `python agent.py` for happy path and no-results path.

---

## A Complete Interaction (Step by Step)

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

FitFindr takes a natural language query, parses it with the LLM, searches mock listings, picks the best match, suggests an outfit using the user's wardrobe, and generates a shareable fit card. If search returns nothing, it tells the user what to try differently and stops — it never calls later tools with empty input.

**Step 1 — Parse + Search:**
- LLM parses query → `{description: "vintage graphic tee", size: null, max_price: 30.0}`
- Tool: `search_listings("vintage graphic tee", size=None, max_price=30.0)`
- Returns **3 matching listings** sorted by relevance:
  1. Y2K Baby Tee — Butterfly Print ($18, Depop, excellent)
  2. Vintage Band Tee — Faded Grey ($19, Depop, fair condition)
  3. Graphic Tee — 2003 Tour Bootleg Style ($24, Depop, good)
- Agent picks top result: **Y2K Baby Tee — Butterfly Print — $18, Depop, excellent condition**

**Step 2 — Suggest outfit:**
- Tool: `suggest_outfit(new_item=<band tee dict>, wardrobe=get_example_wardrobe())`
- Returns a string like: *"Pair this with your baggy straight-leg jeans and black combat boots for a classic 90s grunge look. Layer your vintage black denim jacket if it's chilly."*
- (LLM output varies; uses wardrobe piece names from `example_wardrobe`)

**Step 3 — Fit card:**
- Tool: `create_fit_card(outfit=<suggestion string>, new_item=<band tee dict>)`
- Returns a caption like: *"thrifted this faded band tee off depop for $19 and honestly it was made for my baggy jeans 🖤 full fit breakdown in my stories"*

**Final output to user:**
Three Gradio panels show: (1) listing details for the band tee, (2) outfit suggestion referencing wardrobe pieces, (3) shareable fit card caption. Status bar shows success message.

**Error path example:** Query `"designer ballgown size XXS under $5"` → `search_listings` returns `[]` → agent sets error *"No listings matched your search… Try broadening your keywords, size, or budget."* → UI shows error in status/first panel only. `suggest_outfit` is **not** called.
