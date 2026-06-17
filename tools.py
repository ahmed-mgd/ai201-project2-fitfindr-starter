"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    listings = load_listings()

    # Step 1: apply the optional hard filters first (price, then size).
    candidates = []
    for item in listings:
        if max_price is not None and item["price"] > max_price:
            continue
        if size is not None and size.lower() not in item["size"].lower():
            continue
        candidates.append(item)

    # Step 2: score each remaining listing by keyword overlap. We compare the
    # words in `description` against the title, description, and style tags.
    keywords = [word for word in description.lower().split() if word]

    scored = []
    for item in candidates:
        haystack = " ".join(
            [
                item["title"].lower(),
                item["description"].lower(),
                " ".join(tag.lower() for tag in item["style_tags"]),
            ]
        )
        score = sum(1 for word in keywords if word in haystack)
        if score > 0:
            scored.append((score, item))

    # Step 3: sort by score, highest first, and return just the listing dicts.
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _score, item in scored]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    # Pull the details the LLM needs to describe the new item.
    item_line = (
        f"{new_item.get('title', 'an item')} "
        f"(category: {new_item.get('category', 'unknown')}, "
        f"colors: {', '.join(new_item.get('colors', [])) or 'unspecified'}, "
        f"style: {', '.join(new_item.get('style_tags', [])) or 'unspecified'})"
    )

    items = wardrobe.get("items", [])

    if not items:
        # Empty-wardrobe branch: no pieces to name, so ask for general advice.
        prompt = (
            "A shopper is considering this secondhand item:\n"
            f"{item_line}\n\n"
            "They have not told us what is in their closet yet. Give one or two "
            "short, practical outfit ideas for this item on its own. Mention what "
            "kinds of pieces pair well with it and what vibe it suits. Keep it to "
            "a few sentences and do not invent specific items they own."
        )
    else:
        # Populated-wardrobe branch: list the pieces so the LLM can name them.
        wardrobe_lines = []
        for w in items:
            colors = ", ".join(w.get("colors", [])) or "unspecified"
            tags = ", ".join(w.get("style_tags", [])) or "unspecified"
            wardrobe_lines.append(
                f"- {w.get('name', 'item')} (category: {w.get('category', 'unknown')}, "
                f"colors: {colors}, style: {tags})"
            )
        wardrobe_block = "\n".join(wardrobe_lines)
        prompt = (
            "A shopper is considering this secondhand item:\n"
            f"{item_line}\n\n"
            "Here is what is already in their closet:\n"
            f"{wardrobe_block}\n\n"
            "Suggest one or two complete outfits that pair the new item with "
            "specific pieces from their closet. Name the closet pieces you use. "
            "Add one short styling tip (how to cuff, tuck, or layer). Keep it to "
            "a few sentences and do not invent pieces they do not own."
        )

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are a thoughtful thrift stylist who gives "
                    "concrete, wearable outfit advice.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
        )
        suggestion = response.choices[0].message.content.strip()
        if suggestion:
            return suggestion
    except Exception as err:
        # Fall through to the fallback below rather than crashing the agent.
        print(f"[suggest_outfit] LLM call failed: {err}")

    # Fallback: build a basic styling line from the item's own style tags so the
    # caller always gets a non-empty, useful string.
    tags = ", ".join(new_item.get("style_tags", [])) or "versatile"
    return (
        f"Style the {new_item.get('title', 'piece')} around its {tags} feel. "
        "Pair it with simple, neutral basics and let the piece be the focus."
    )


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    # Guard: without an outfit there is nothing to caption.
    if not outfit or not outfit.strip():
        return (
            "Can't write a fit card without an outfit suggestion. "
            "Run suggest_outfit first and pass its result here."
        )

    title = new_item.get("title", "this piece")
    price = new_item.get("price")
    price_str = f"${price:.0f}" if isinstance(price, (int, float)) else "a steal"
    platform = new_item.get("platform", "secondhand")

    prompt = (
        "Write a short, casual caption for an outfit photo, the kind someone "
        "posts on Instagram or TikTok. Here are the details:\n"
        f"- Item: {title}\n"
        f"- Price: {price_str}\n"
        f"- Where I found it: {platform}\n"
        f"- The outfit: {outfit}\n\n"
        "Rules: 2 to 4 sentences. Mention the item, the price, and the platform "
        "once each, woven in naturally. Capture the vibe of the outfit in specific "
        "words. Sound like a real person, not a product description. A relevant "
        "emoji or two is fine."
    )

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You write punchy, authentic outfit captions for "
                    "secondhand fashion finds.",
                },
                {"role": "user", "content": prompt},
            ],
            # Higher temperature so the caption reads differently each run.
            temperature=1.0,
        )
        caption = response.choices[0].message.content.strip()
        if caption:
            return caption
    except Exception as err:
        print(f"[create_fit_card] LLM call failed: {err}")

    # Fallback caption so the user still gets something shareable on LLM failure.
    return (
        f"thrifted this {title} off {platform} for {price_str} and i'm obsessed. "
        "styled it up and it's going straight into the rotation."
    )
