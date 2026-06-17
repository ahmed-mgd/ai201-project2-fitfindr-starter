# FitFindr — Triggered Failure Modes

This file records each tool's failure mode being deliberately triggered, with
the exact command run and the actual output. Use it as a reference for the demo
video. Every failure returns a specific, useful response instead of raising an
exception or returning nothing.

---

## 1. search_listings returns no matches

A query that matches nothing in the dataset.

Command:

```bash
python -c "from tools import search_listings; print(search_listings('designer ballgown', size='XXS', max_price=5))"
```

Output:

```
[]
```

It returns an empty list, not an exception. When the full agent runs the same
impossible query, the planning loop catches the empty list and stops before
calling the other tools:

```bash
python -c "
from agent import run_agent
from utils.data_loader import get_example_wardrobe
s = run_agent('designer ballgown size XXS under \$5', get_example_wardrobe())
print(s['error'])
print(s['fit_card'])
"
```

Output:

```
No listings matched 'designer ballgown' in size XXS under $5. Try removing the size filter, raising your budget, or using different keywords.
None
```

The user is told what was searched and what to try next. `fit_card` stays None
because `suggest_outfit` and `create_fit_card` are never called on empty input.

---

## 2. suggest_outfit with an empty wardrobe

A new user with nothing in their closet.

Command:

```bash
python -c "
from tools import search_listings, suggest_outfit
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe
results = search_listings('vintage graphic tee', size=None, max_price=50)
print(suggest_outfit(results[0], get_empty_wardrobe()))
"
```

Output (one sample run):

```
This Y2K baby tee is perfect for creating a playful, nostalgic look. On its own, it could be styled with a flowy skirt for a whimsical, cottagecore vibe or with distressed denim for a more casual, vintage-inspired look. The tee's pastel colors and graphic print pair well with neutral or earthy tones, and its relaxed fit suits laid-back, effortless outfits.
```

Instead of failing on the empty wardrobe, the tool switches to general styling
advice and returns a useful, non-empty string.

---

## 3. create_fit_card with an empty outfit string

The outfit input is missing.

Command:

```bash
python -c "
from tools import search_listings, create_fit_card
results = search_listings('vintage graphic tee', size=None, max_price=50)
print(create_fit_card('', results[0]))
"
```

Output:

```
Can't write a fit card without an outfit suggestion. Run suggest_outfit first and pass its result here.
```

It returns a descriptive message string, not a Python exception.

---

## Automated coverage

These same failure modes are also covered by the pytest suite in
`tests/test_tools.py`:

- `test_search_empty_results` — empty list on no match
- `test_suggest_outfit_empty_wardrobe` — non-empty string on empty wardrobe
- `test_create_fit_card_empty_outfit` and `test_create_fit_card_whitespace_outfit`
  — message string on missing outfit

Run them all with:

```bash
pytest tests/
```
