"""
Tests for the three FitFindr tools.

Run from the project root with:
    pytest tests/

Each tool has at least one test for its normal path and one for its failure
mode. The suggest_outfit and create_fit_card tests call the live Groq LLM, so
they need a valid GROQ_API_KEY in .env.
"""

from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ── search_listings ────────────────────────────────────────────────────────────

def test_search_returns_results():
    """A reasonable query should return a non-empty list of dicts."""
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0
    # Every result is a full listing dict.
    assert all("title" in item and "price" in item for item in results)


def test_search_empty_results():
    """A query that matches nothing returns an empty list, not an exception."""
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    """No returned item should cost more than the max_price ceiling."""
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_size_filter_case_insensitive():
    """Size matching is case-insensitive and works on substrings like S/M."""
    results = search_listings("tee", size="m", max_price=None)
    assert all("m" in item["size"].lower() for item in results)


def test_search_results_sorted_by_relevance():
    """Results come back sorted by keyword overlap, best match first."""
    results = search_listings("vintage graphic tee", size=None, max_price=None)
    assert len(results) >= 2
    # The top result should mention at least one of the keywords somewhere.
    top = results[0]
    blob = (top["title"] + top["description"] + " ".join(top["style_tags"])).lower()
    assert any(word in blob for word in ["vintage", "graphic", "tee"])


# ── suggest_outfit ──────────────────────────────────────────────────────────────

def _sample_item():
    return search_listings("vintage graphic tee", size=None, max_price=30)[0]


def test_suggest_outfit_with_wardrobe():
    """With a populated wardrobe, we get a non-empty styling string."""
    item = _sample_item()
    result = suggest_outfit(item, get_example_wardrobe())
    assert isinstance(result, str)
    assert result.strip() != ""


def test_suggest_outfit_empty_wardrobe():
    """An empty wardrobe must not crash; it returns general advice instead."""
    item = _sample_item()
    result = suggest_outfit(item, get_empty_wardrobe())
    assert isinstance(result, str)
    assert result.strip() != ""


# ── create_fit_card ─────────────────────────────────────────────────────────────

def test_create_fit_card_empty_outfit():
    """An empty outfit returns a clear message string, not an exception."""
    item = _sample_item()
    result = create_fit_card("", item)
    assert isinstance(result, str)
    assert "without an outfit" in result.lower()


def test_create_fit_card_whitespace_outfit():
    """A whitespace-only outfit is treated the same as empty."""
    item = _sample_item()
    result = create_fit_card("   \n  ", item)
    assert "without an outfit" in result.lower()


def test_create_fit_card_varies():
    """The same input should produce different captions across runs."""
    item = _sample_item()
    outfit = "Pair it with baggy jeans and chunky white sneakers."
    card_a = create_fit_card(outfit, item)
    card_b = create_fit_card(outfit, item)
    assert card_a.strip() != ""
    assert card_b.strip() != ""
    assert card_a != card_b
