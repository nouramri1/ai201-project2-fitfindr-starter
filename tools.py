"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

from __future__ import annotations

import os
import re

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()

LLM_MODEL = "llama-3.3-70b-versatile"


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


def _call_llm(system_prompt: str, user_prompt: str, temperature: float = 0.7) -> str:
    """Send a chat completion request to Groq and return the assistant text."""
    client = _get_groq_client()
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
    )
    return response.choices[0].message.content.strip()


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def _listing_search_text(listing: dict) -> str:
    """Combine listing fields into one searchable string."""
    tags = " ".join(listing.get("style_tags", []))
    colors = " ".join(listing.get("colors", []))
    brand = listing.get("brand") or ""
    return " ".join(
        [
            listing.get("title", ""),
            listing.get("description", ""),
            listing.get("category", ""),
            tags,
            colors,
            brand,
        ]
    ).lower()


def _description_phrases(description: str) -> list[str]:
    """Extract meaningful multi-word phrases from the search description."""
    words = [word.lower() for word in re.findall(r"\w+", description) if word]
    phrases = []
    for i in range(len(words) - 1):
        phrases.append(f"{words[i]} {words[i + 1]}")
    if len(words) >= 3:
        phrases.append(f"{words[0]} {words[1]} {words[2]}")
    return phrases


def _score_listing(listing: dict, keywords: list[str], phrases: list[str]) -> int:
    """
    Score a listing by keyword and phrase overlap.
    All keywords must appear in the listing text to be considered a match.
    """
    searchable = _listing_search_text(listing)
    if not keywords or not all(kw in searchable for kw in keywords):
        return 0

    score = len(keywords)
    for phrase in phrases:
        if phrase in searchable:
            score += 2
    return score


def _sort_key(listing: dict, score: int) -> tuple:
    """Sort by relevance, prefer band/graphic tees, then lower price."""
    tags = " ".join(listing.get("style_tags", [])).lower()
    title = listing.get("title", "").lower()
    band_rank = 0 if "band tee" in tags or "band" in title else 1
    return (-score, band_rank, listing.get("price", 0))


def _matches_size(listing_size: str, requested_size: str) -> bool:
    """Case-insensitive substring match (e.g. 'M' matches 'S/M')."""
    return requested_size.lower() in listing_size.lower()


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.
    """
    listings = load_listings()

    if max_price is not None:
        listings = [item for item in listings if item["price"] <= max_price]

    if size:
        listings = [
            item for item in listings if _matches_size(item["size"], size)
        ]

    keywords = [word.lower() for word in re.findall(r"\w+", description) if word]
    if not keywords:
        return []

    phrases = _description_phrases(description)
    scored = [
        (item, _score_listing(item, keywords, phrases))
        for item in listings
    ]
    scored = [(item, score) for item, score in scored if score > 0]
    scored.sort(key=lambda pair: _sort_key(pair[0], pair[1]))
    return [item for item, _ in scored]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.
    """
    items = wardrobe.get("items", [])
    item_summary = (
        f"Title: {new_item.get('title')}\n"
        f"Category: {new_item.get('category')}\n"
        f"Style tags: {', '.join(new_item.get('style_tags', []))}\n"
        f"Colors: {', '.join(new_item.get('colors', []))}\n"
        f"Description: {new_item.get('description')}"
    )

    if not items:
        system_prompt = (
            "You are a personal stylist. The user has an empty wardrobe and is "
            "considering buying a thrifted item. Suggest 1–2 complete outfit ideas "
            "using general pieces they could look for (not specific wardrobe items). "
            "Be concise, friendly, and specific about vibe and pairing."
        )
        user_prompt = (
            f"The user is considering this thrift find:\n\n{item_summary}\n\n"
            "What kinds of outfits would work with this piece?"
        )
    else:
        wardrobe_lines = "\n".join(
            f"- {piece['name']} ({piece['category']}, "
            f"{', '.join(piece.get('style_tags', []))})"
            for piece in items
        )
        system_prompt = (
            "You are a personal stylist. Suggest 1–2 complete outfits that combine "
            "the thrifted item with specific pieces from the user's existing wardrobe. "
            "Name wardrobe pieces by their exact names. Be concise and practical."
        )
        user_prompt = (
            f"Thrift find:\n{item_summary}\n\n"
            f"User's wardrobe:\n{wardrobe_lines}\n\n"
            "Suggest outfit combinations using the new item and wardrobe pieces."
        )

    try:
        result = _call_llm(system_prompt, user_prompt, temperature=0.7)
        if result:
            return result
    except Exception:
        pass

    return (
        "Couldn't generate outfit suggestions right now. "
        "Try pairing this piece with basics in a complementary color and silhouette."
    )


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.
    """
    if not outfit or not outfit.strip():
        return (
            "Couldn't create a fit card — outfit suggestion was missing or incomplete."
        )

    item_title = new_item.get("title", "this find")
    item_price = new_item.get("price", 0)
    item_platform = new_item.get("platform", "thrift")

    system_prompt = (
        "Write a casual, authentic Instagram/TikTok outfit caption (2–4 sentences). "
        "Sound like a real OOTD post, not a product listing. Mention the item name, "
        "price, and platform naturally once each. Capture the outfit vibe in specific terms."
    )
    user_prompt = (
        f"Item: {item_title}\n"
        f"Price: ${item_price:.2f}\n"
        f"Platform: {item_platform}\n\n"
        f"Outfit idea:\n{outfit}\n\n"
        "Write the fit card caption."
    )

    try:
        result = _call_llm(system_prompt, user_prompt, temperature=0.9)
        if result:
            return result
    except Exception:
        pass

    return (
        "Couldn't generate a fit card right now. Please try again."
    )
