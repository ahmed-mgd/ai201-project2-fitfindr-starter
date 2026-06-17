# FitFindr 🛍️

FitFindr is a multi-tool AI agent that helps you find secondhand clothing and
figure out how to wear it. You type a plain language request like "vintage
graphic tee under $30". The agent searches a mock listings dataset, suggests an
outfit using pieces from your wardrobe, and writes a short caption you could
post with the look. It also handles the cases where a tool finds nothing or gets
bad input, so it stays useful instead of crashing.

## What's Included

```
ai201-project2-fitfindr-starter/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # Wardrobe format + example wardrobe
├── utils/
│   └── data_loader.py         # Helper functions for loading the data
├── tools.py                   # The three tools
├── agent.py                   # The planning loop and session state
├── app.py                     # Gradio interface
├── tests/test_tools.py        # pytest tests for each tool and failure mode
├── FAILURE_MODES.md           # Triggered failure modes with captured output
├── planning.md                # The spec written before any code
└── requirements.txt           # Python dependencies
```

## Setup

**macOS / Linux:**
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows:**
```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
```

Set your Groq API key in a `.env` file (get a free key at [console.groq.com](https://console.groq.com)):
```
GROQ_API_KEY=your_key_here
```

## Running It

Run the web app:
```bash
python app.py
```
Open the URL shown in your terminal. It is usually http://localhost:7860, but if
that port is busy Gradio will pick the next one (for example 7861), so check the
terminal output for the exact address.

Run the agent from the command line instead:
```bash
python agent.py
```

Run the tests:
```bash
pytest tests/
```

---

## Tool Inventory

The agent uses three tools. The signatures here match the actual functions in
[`tools.py`](tools.py).

### `search_listings(description, size=None, max_price=None) -> list[dict]`

**Purpose:** Search the 40-item mock dataset and return the listings that match
what the user asked for.

**Inputs:**
- `description` (str): Keywords describing the wanted item, for example
  "vintage graphic tee". This drives the relevance scoring and is required.
- `size` (str or None): A size to filter by, for example "M". Matching is
  case-insensitive and uses a substring, so "M" matches "S/M". Pass None to skip
  the size filter.
- `max_price` (float or None): An inclusive price ceiling. A listing passes only
  if its price is less than or equal to this. Pass None to skip the price filter.

**Output:** A list of listing dicts sorted by relevance, best match first. Each
dict has the full fields: `id`, `title`, `description`, `category`,
`style_tags` (list), `size`, `condition`, `price` (float), `colors` (list),
`brand`, and `platform`. Listings that score zero keyword overlap are dropped.
Returns an empty list when nothing matches.

### `suggest_outfit(new_item, wardrobe) -> str`

**Purpose:** Take the found item and the user's closet and suggest one or two
complete outfits. This is the step that turns a single listing into a look the
user can picture wearing.

**Inputs:**
- `new_item` (dict): A listing dict, normally the top result from
  `search_listings`. The tool reads its title, category, colors, and style tags.
- `wardrobe` (dict): A wardrobe dict shaped like `{"items": [...]}`, where each
  item has `name`, `category`, `colors`, `style_tags`, and optional `notes`. The
  list may be empty.

**Output:** A non-empty string with outfit ideas. When the wardrobe has items,
the suggestions name specific pieces from it. When the wardrobe is empty, the
string is general styling advice for the item instead. This tool calls the Groq
LLM (`llama-3.3-70b-versatile`).

### `create_fit_card(outfit, new_item) -> str`

**Purpose:** Turn the outfit suggestion and the found item into a short, casual
caption, the kind of thing you would post with an outfit photo.

**Inputs:**
- `outfit` (str): The outfit suggestion string from `suggest_outfit`.
- `new_item` (dict): The listing dict for the found item. The tool pulls the
  title, price, and platform from it.

**Output:** A 2 to 4 sentence caption string. It names the item, mentions the
price and platform once each, and reads casually instead of like a product
description. The LLM runs at a higher temperature so the caption is different
each time for different inputs.

---

## Planning Loop

The agent does not call all three tools in a fixed order no matter what. It runs
a series of steps, and each step looks at what the last step produced before
deciding whether to keep going. The loop lives in `run_agent()` in
[`agent.py`](agent.py). Here is what it decides at each point.

1. **Parse the query.** It reads the user's text and pulls out a description, an
   optional size, and an optional max price using simple regex rules. It first
   trims any trailing clause about what the user normally wears (like "I mostly
   wear baggy jeans"), since that describes the wardrobe and not the item, then
   drops filler words so the leftover keywords are about the item. The result is
   stored in `session["parsed"]`.

2. **Search, then branch.** It calls `search_listings` with the parsed values and
   stores the result in `session["search_results"]`. This is the first decision
   point. If the list is empty, the agent sets a helpful message in
   `session["error"]` and returns right away. It does not call the next two tools
   with empty input. If the list has matches, it continues.

3. **Select the item.** It sets `session["selected_item"]` to the top result,
   `search_results[0]`.

4. **Suggest an outfit.** It calls `suggest_outfit` with the selected item and the
   wardrobe and stores the result in `session["outfit_suggestion"]`. The
   empty-wardrobe case is handled inside the tool, so the loop does not need a
   separate branch for it, but it does check that the returned string is not
   empty. If it somehow is, it sets an error and returns.

5. **Make the fit card.** It calls `create_fit_card` with the outfit suggestion
   and the selected item and stores the result in `session["fit_card"]`.

6. **Return the session.** The run is done when `fit_card` is filled in, or
   earlier if an error was set at any checkpoint.

So the behavior changes with the input. An empty search ends the run early with
an error and no later calls. A search with matches drives the selected item
through the rest of the flow. An empty wardrobe quietly changes what
`suggest_outfit` produces without stopping the run.

---

## State Management

All the information for one interaction lives in a single session dict, created
by `_new_session(query, wardrobe)` in [`agent.py`](agent.py). Every step reads
from this dict and writes back to it, so there is one place that holds the truth
about the run. The fields are:

- `query`: the original user text.
- `parsed`: the description, size, and max_price pulled from the query.
- `search_results`: the list returned by `search_listings`.
- `selected_item`: the top listing, which flows into the next two tools.
- `wardrobe`: the user's closet, read by `suggest_outfit`.
- `outfit_suggestion`: the string returned by `suggest_outfit`.
- `fit_card`: the caption returned by `create_fit_card`.
- `error`: None on success, or a user-facing message if the run ended early.

The hand-off works like a relay. `search_listings` writes `search_results`, the
loop copies `search_results[0]` into `selected_item`, and `suggest_outfit` reads
`selected_item` straight from the session. The user never has to retype the item.
`create_fit_card` then reads `outfit_suggestion` and `selected_item` from the
same dict. Because everything sits in one object, you can read the whole
interaction at the end by looking at the returned session.

You can see this in practice. After a run, `session["selected_item"]` is the
exact same dict as `session["search_results"][0]` (verified with an identity
check, `selected_item is search_results[0]` returns True), and that same dict is
what gets passed into both later tools.

---

## Interaction Walkthrough

**User query:** "I'm looking for a vintage graphic tee under $30. I mostly wear
baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1 — Tool called:**
- Tool: `search_listings`
- Input: `description="vintage graphic tee", size=None, max_price=30.0`
- Why this tool: The user is asking what is out there, so the agent searches
  first. The parser trims the "I mostly wear..." clause, so the wardrobe details
  do not become search keywords, and it finds the $30 ceiling.
- Output: A list of matching tees under $30, sorted by relevance. The top result
  is the Y2K Baby Tee, Butterfly Print, $18, from depop.

**Step 2 — Tool called:**
- Tool: `suggest_outfit`
- Input: `new_item=<the Y2K Baby Tee dict>, wardrobe=<example wardrobe>`
- Why this tool: The search returned matches, so the agent selected the top one
  and now styles it against the user's closet.
- Output: An outfit idea such as pairing the tee with the user's baggy
  straight-leg jeans and chunky white sneakers, with a tip to tuck the front.

**Step 3 — Tool called:**
- Tool: `create_fit_card`
- Input: `outfit=<the suggestion from Step 2>, new_item=<the Y2K Baby Tee dict>`
- Why this tool: There is now a complete outfit, so the agent writes a shareable
  caption for it.
- Output: A casual caption that names the tee, the $18 price, and depop once
  each.

**Final output to user:** The UI shows the found listing in the first panel, the
outfit idea in the second panel, and the fit card caption in the third panel.

---

## Error Handling and Fail Points

Every tool handles its own failure mode. None of them crash the agent or fail
silently. There is a full record of these being triggered, with captured output,
in [`FAILURE_MODES.md`](FAILURE_MODES.md).

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| `search_listings` | No listing matches the query | The tool returns an empty list. The planning loop catches it, sets a specific message in `session["error"]` that names what was searched and what to change, and returns before calling the other tools. |
| `suggest_outfit` | The wardrobe is empty | The tool detects `wardrobe["items"] == []` and switches to a general-advice prompt, returning styling ideas for the item on its own instead of an error or empty string. If the LLM call fails, it returns a short fallback line built from the item's style tags. |
| `create_fit_card` | The outfit input is missing or only whitespace | The tool returns a clear message string telling the caller to run `suggest_outfit` first, rather than raising. If the LLM call fails, it returns a simple fallback caption built from the item's title, price, and platform. |

**Concrete example from testing.** I ran the impossible query "designer ballgown
size XXS under $5" through the full agent. `search_listings` returned `[]`, the
loop set this error and stopped, and `fit_card` stayed `None`:

```
session['error']    -> No listings matched 'designer ballgown' in size XXS under $5.
                       Try removing the size filter, raising your budget, or using
                       different keywords.
session['fit_card'] -> None
```

`suggest_outfit` and `create_fit_card` were never called, which is the point of
the early return.

---

## AI Usage

I used Claude to help write the code, one piece at a time, and I checked each
result against my spec in [`planning.md`](planning.md) before keeping it.

**Instance 1 — `search_listings`.** I gave Claude the Tool 1 block from
planning.md (the inputs, the return shape, and the rule that it returns an empty
list instead of raising), plus the docstring already in `tools.py`. It produced a
function that filtered by price and size and scored by keyword overlap. I checked
it against my spec and confirmed it used `load_listings()` from the data loader,
filtered by all three parameters, did case-insensitive substring matching on
size, dropped zero-score listings, and returned `[]` on no match. I then tested
it with a normal query, a no-match query, and a price-only query to make sure all
three behaved.

**Instance 2 — the planning loop in `agent.py`.** I gave Claude the Planning Loop
and State Management sections and the ASCII diagram from planning.md, and asked it
to implement `run_agent()` to match those steps. The first version kept the
"I mostly wear baggy jeans" clause in the search description, which pushed the
wrong item to the top. That did not match my walkthrough, where the wardrobe text
should not become search keywords, so I overrode it and added a rule to the
parser that trims the "what I wear" clause and drops conversational filler before
searching. After that change, the parsed description matched my spec and the
correct item came back on top.

---

## Spec Reflection

**One way planning.md helped during implementation:**
Writing the planning loop as numbered branches before coding meant I already knew
exactly where the early return for an empty search had to go. When I implemented
`run_agent()`, I was not deciding the control flow on the fly. I was copying the
branch I had already described, which is why the no-results path worked correctly
on the first real test.

**One divergence from your spec, and why:**
My planning.md said the parser would simply keep "vintage graphic tee" as the
description and not parse the wardrobe text into the search. The first
implementation did not actually do that. It left the "I mostly wear baggy jeans
and chunky sneakers" words in the description, which changed the top search
result. I had to add a real rule to the parser to trim that clause and to drop
filler words and one-letter tokens. The spec described the behavior I wanted, but
I had underestimated how much parsing work it would take to get there, so the
code grew a step the plan did not mention.
