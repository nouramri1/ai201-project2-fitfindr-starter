"""Tests for FitFindr tools — run with: pytest tests/"""

from tools import create_fit_card, search_listings, suggest_outfit
from utils.data_loader import get_empty_wardrobe


def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_vintage_graphic_tee_top_three():
    results = search_listings("vintage graphic tee", max_price=30.0)
    assert len(results) >= 3
    titles = [item["title"] for item in results[:3]]
    assert any("tee" in title.lower() for title in titles)


def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_size_filter():
    results = search_listings("vintage graphic tee", size="M", max_price=30.0)
    assert all("m" in item["size"].lower() for item in results)


def test_suggest_outfit_empty_wardrobe():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    advice = suggest_outfit(results[0], get_empty_wardrobe())
    assert isinstance(advice, str)
    assert len(advice.strip()) > 0


def test_create_fit_card_empty_outfit():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    message = create_fit_card("", results[0])
    assert isinstance(message, str)
    assert "missing" in message.lower() or "couldn't" in message.lower()
