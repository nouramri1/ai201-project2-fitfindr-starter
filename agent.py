"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.
"""

import json

from tools import _get_groq_client, create_fit_card, search_listings, suggest_outfit

LLM_MODEL = "llama-3.3-70b-versatile"


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """Initialize and return a fresh session dict for one user interaction."""
    return {
        "query": query,
        "parsed": {},
        "search_results": [],
        "selected_item": None,
        "wardrobe": wardrobe,
        "outfit_suggestion": None,
        "fit_card": None,
        "error": None,
    }


# ── query parsing (LLM) ───────────────────────────────────────────────────────

def _parse_query(query: str) -> dict:
    """
    Use Groq to extract description, size, and max_price from natural language.
    Returns dict with keys: description (str), size (str|None), max_price (float|None).
    """
    client = _get_groq_client()
    system_prompt = (
        "Extract shopping search parameters from the user's message. "
        "Return JSON with exactly these keys:\n"
        '- "description": string — keywords for what they want (e.g. "vintage graphic tee")\n'
        '- "size": string or null — clothing size if mentioned (e.g. "M", "8")\n'
        '- "max_price": number or null — maximum price in dollars if mentioned\n'
        "Only include size and max_price when the user clearly specifies them."
    )

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )

    parsed = json.loads(response.choices[0].message.content)
    description = (parsed.get("description") or query).strip()
    size = parsed.get("size")
    max_price = parsed.get("max_price")

    if size is not None:
        size = str(size).strip() or None
    if max_price is not None:
        max_price = float(max_price)

    return {
        "description": description,
        "size": size,
        "max_price": max_price,
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.
    """
    session = _new_session(query, wardrobe)

    try:
        session["parsed"] = _parse_query(query)
    except Exception:
        session["error"] = (
            "Couldn't understand your search request. "
            "Try something like: vintage graphic tee under $30, size M."
        )
        return session

    parsed = session["parsed"]
    session["search_results"] = search_listings(
        description=parsed["description"],
        size=parsed.get("size"),
        max_price=parsed.get("max_price"),
    )

    if not session["search_results"]:
        session["error"] = (
            f"No listings matched your search for "
            f"'{parsed['description']}'"
            + (f" in size {parsed['size']}" if parsed.get("size") else "")
            + (f" under ${parsed['max_price']:.0f}" if parsed.get("max_price") else "")
            + ". Try broadening your keywords, size, or budget."
        )
        return session

    session["selected_item"] = session["search_results"][0]

    outfit = suggest_outfit(session["selected_item"], wardrobe)
    if not outfit or not outfit.strip():
        session["error"] = (
            "Couldn't generate outfit suggestions right now. Please try again."
        )
        return session
    session["outfit_suggestion"] = outfit

    fit_card = create_fit_card(outfit, session["selected_item"])
    if fit_card.startswith("Couldn't"):
        session["error"] = fit_card
        return session
    session["fit_card"] = fit_card

    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
