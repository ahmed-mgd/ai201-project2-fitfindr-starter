# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Searches the 40-item mock listings dataset for pieces that match what the user described, then narrows by size and price when those are given. It scores each remaining listing by how many of the user's keywords show up in its title, description, and style tags, and returns the matches sorted with the best one first.

**Input parameters:**
- `description` (str): Free-text keywords describing the wanted item, for example "vintage graphic tee". This is the only required parameter and it drives the relevance scoring.
- `size` (str or None): A size string to filter by, such as "M". Matching is case-insensitive and treats a listing as a match if the size appears anywhere in its size field, so "M" matches "S/M". Pass None to skip size filtering.
- `max_price` (float or None): An inclusive price ceiling. A listing passes only if its price is less than or equal to this number. Pass None to skip price filtering.

**What it returns:**
A list of listing dicts sorted by relevance score, highest first. Each dict carries the full listing fields: `id`, `title`, `description`, `category`, `style_tags` (list), `size`, `condition`, `price` (float), `colors` (list), `brand`, and `platform`. Listings that score zero on keyword overlap are dropped, so every item in the list is an actual match. Returns an empty list when nothing matches rather than raising an exception.

**What happens if it fails or returns nothing:**
The tool itself never raises; it returns `[]` on no matches. The planning loop is responsible for catching the empty list, writing a helpful error into the session, and returning early so the later tools are never called with an empty selection.

---

### Tool 2: suggest_outfit

**What it does:**
Takes the item the user found and the pieces already in their closet, then asks the LLM to put together one or two complete outfits that pair the new item with named wardrobe pieces. It is the step that turns a single listing into something the user can actually picture wearing.

**Input parameters:**
- `new_item` (dict): A single listing dict, normally the top result from `search_listings`. The function reads its title, category, colors, and style tags so the LLM knows what it is styling.
- `wardrobe` (dict): A wardrobe dict shaped like `{"items": [...]}`, where each item has `name`, `category`, `colors`, `style_tags`, and optional `notes`. This may be empty, so the function checks the length of `wardrobe["items"]` before building its prompt.

**What it returns:**
A non-empty string with one or two outfit ideas written in plain language, naming specific wardrobe pieces to pair with the new item along with a short styling tip. When the wardrobe has items, the suggestions reference those pieces by name. When the wardrobe is empty, the string is general styling advice for the item instead.

**What happens if it fails or returns nothing:**
If `wardrobe["items"]` is empty, the tool does not fail; it switches to a general-advice prompt and still returns useful styling ideas. If the LLM call raises or comes back empty, the tool returns a short fallback styling string built from the item's own style tags so the agent stays useful and never returns an empty string.

---

### Tool 3: create_fit_card

**What it does:**
Turns the outfit suggestion and the found item into a short, casual caption that someone would actually post under an outfit photo. It runs the LLM at a higher temperature so the caption reads differently for different items and outfits rather than sounding like a product blurb.

**Input parameters:**
- `outfit` (str): The outfit suggestion string returned by `suggest_outfit`. This gives the caption its vibe and the pieces it references.
- `new_item` (dict): The listing dict for the found item. The function pulls the title, price, and platform from it so the caption can mention the find naturally.

**What it returns:**
A 2 to 4 sentence string written like a real outfit post. It names the item, mentions the price and platform once each, captures the outfit's mood in specific words, and reads casually rather than like marketing copy. Because the temperature is raised, different inputs produce noticeably different captions.

**What happens if it fails or returns nothing:**
If `outfit` is missing, empty, or only whitespace, the tool does not raise; it returns a short descriptive error string telling the caller the outfit input was empty so the agent can surface that. If the LLM call itself fails, it returns a simple fallback caption built from the item's title, price, and platform so the user still gets something shareable.

---

### Additional Tools (if any)

None. I am building the three required tools only and not doing any stretch features.

---

## Planning Loop

**How does your agent decide which tool to call next?**

The loop runs as a series of steps where each step looks at what the previous step put into the session before deciding whether to continue. It is not a fixed three-call sequence, because two checkpoints can end the run early.

1. Parse the query. The agent reads `session["query"]` and extracts a description, an optional size, and an optional max_price, storing them in `session["parsed"]`. I will parse with simple Python: a regex for a dollar amount to get max_price, a regex for a size token like "size M" to get size, and the leftover text as the description.

2. Call `search_listings(description, size, max_price)` and store the result in `session["search_results"]`. Branch on the result: if the list is empty, write a specific message into `session["error"]` (telling the user what was searched and to loosen size or raise the budget) and return the session immediately. The agent does not call `suggest_outfit` on empty input. If the list is non-empty, set `session["selected_item"] = session["search_results"][0]` and continue.

3. Call `suggest_outfit(selected_item, wardrobe)` and store the result in `session["outfit_suggestion"]`. This tool handles the empty-wardrobe case itself by returning general advice, so the loop does not need a separate branch here, but it does check that the returned string is non-empty before moving on. If it somehow comes back empty, set `session["error"]` and return.

4. Call `create_fit_card(outfit_suggestion, selected_item)` and store the result in `session["fit_card"]`.

5. Return the session. The agent knows it is done when `fit_card` is filled in, or earlier if `error` was set at any checkpoint.

The behavior changes based on what comes back: an empty search ends the run with an error and no later calls, a non-empty search drives the selected item forward, and an empty wardrobe quietly changes what `suggest_outfit` produces without stopping the run.

---

## State Management

**How does information from one tool get passed to the next?**

All state for a single interaction lives in one session dict created by `_new_session(query, wardrobe)` in [agent.py](agent.py). This dict is the single source of truth, and every step reads from it and writes back to it rather than passing long argument chains around. The tracked fields are:

- `query`: the original user request, set at the start.
- `parsed`: the `description`, `size`, and `max_price` pulled out of the query.
- `search_results`: the list returned by `search_listings`.
- `selected_item`: the top listing the agent picked, which is what flows into the next two tools.
- `wardrobe`: the user's closet, passed in once and read by `suggest_outfit`.
- `outfit_suggestion`: the string returned by `suggest_outfit`.
- `fit_card`: the final caption returned by `create_fit_card`.
- `error`: stays None on success, or holds a user-facing message if the run ended early.

The hand-off works like a relay. `search_listings` writes `search_results`, the loop copies `search_results[0]` into `selected_item`, and `suggest_outfit` then reads `selected_item` and `wardrobe` straight from the session, so the user never has to retype the item. `create_fit_card` reads `outfit_suggestion` and `selected_item` from the same dict. Because everything sits in one place, the caller can inspect the whole interaction afterward by reading the returned session.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | The loop sets `session["error"]` to a specific message that names what was searched and offers a concrete fix, for example "No listings matched 'vintage graphic tee' under $30 in size M. Try removing the size filter or raising your budget." It then returns early and never calls the next two tools with empty input. |
| suggest_outfit | Wardrobe is empty | The tool detects `wardrobe["items"] == []` and switches to a general-advice prompt, returning styling ideas for the item on its own (what to pair it with, what vibe it suits) instead of erroring or returning an empty string. If the LLM call also fails, it returns a short fallback string built from the item's style tags. |
| create_fit_card | Outfit input is missing or incomplete | If `outfit` is empty or whitespace, the tool returns a clear message like "Can't write a fit card without an outfit suggestion." rather than raising. If the LLM call fails, it returns a simple fallback caption built from the item's title, price, and platform so the user still gets something shareable. |

---

## Architecture

```
User query + wardrobe
    │
    ▼
_new_session(query, wardrobe)  ──►  Session dict (single source of truth)
    │                                 query, parsed, search_results,
    │                                 selected_item, wardrobe,
    ▼                                 outfit_suggestion, fit_card, error
Planning Loop ───────────────────────────────────────────────────────────┐
    │                                                                      │
    │  parse query  →  Session: parsed = {description, size, max_price}    │
    │                                                                      │
    ├─► search_listings(description, size, max_price)                      │
    │       │ results = []                                                 │
    │       ├──► [ERROR] Session: error = "No listings matched ..." ──────►│
    │       │                                                              │
    │       │ results = [item, ...]                                        │
    │       ▼                                                              │
    │   Session: search_results = [...]; selected_item = results[0]        │
    │       │                                                              │
    │       │ selected_item + wardrobe                                     │
    ├─► suggest_outfit(selected_item, wardrobe)                            │
    │       │ wardrobe empty  →  general styling advice (no early return)  │
    │       ▼                                                              │
    │   Session: outfit_suggestion = "..."                                 │
    │       │                                                              │
    │       │ outfit_suggestion + selected_item                            │
    └─► create_fit_card(outfit_suggestion, selected_item)                  │
            │  outfit empty  →  returns error/fallback caption string      │
            ▼                                                              │
        Session: fit_card = "..."                                          │
            │                                              error path returns here
            ▼                                                              │
        Return session  ◄──────────────────────────────────────────────────┘
            │
            ▼
        Caller reads session["error"] first, then fit_card / outfit_suggestion
```

---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**

I will use Claude (Claude Code) for all three tools, one at a time.

- For `search_listings`, I will give Claude the Tool 1 block above (the inputs, the return shape, and the empty-result behavior) plus the docstring already in [tools.py](tools.py), and ask it to implement the function using `load_listings()` from the data loader. Before trusting it I will read the code to confirm it filters by all three parameters, does case-insensitive substring matching on size, drops zero-score listings, and returns `[]` instead of raising. Then I will test it with three queries: a normal one ("graphic tee", size "M", max_price 30), one that should return nothing ("designer ballgown" under $5), and one with no size or price so I can see the filters being skipped.

- For `suggest_outfit`, I will give Claude the Tool 2 block plus the wardrobe schema, and ask it to build the empty-wardrobe branch and the populated-wardrobe branch separately. I will verify by running it once with `get_example_wardrobe()` and once with `get_empty_wardrobe()` and checking that the first names real wardrobe pieces and the second gives general advice, and that neither returns an empty string.

- For `create_fit_card`, I will give Claude the Tool 3 block and the style guidelines, and ask it to raise the temperature and guard against an empty outfit string. I will verify by calling it twice with different items and confirming the captions differ, mention the price and platform once each, and read casually rather than like a product description.

**Milestone 4 — Planning loop and state management:**

I will give Claude the Planning Loop section, the State Management section, and the ASCII diagram from the Architecture section above, and ask it to implement `run_agent()` in [agent.py](agent.py) so it matches those steps exactly. I will check that it parses the query into `session["parsed"]`, returns early with a filled-in `session["error"]` when `search_results` is empty, sets `selected_item = search_results[0]`, and threads state between the tools through the session dict rather than re-deriving it. I will verify against the two cases already stubbed in the `__main__` block: the happy-path graphic tee query should end with a non-empty `fit_card` and `error` of None, and the "designer ballgown size XXS under $5" query should end with a populated `error` and None for the later fields.

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**What FitFindr needs to do (in my own words):**

FitFindr takes a plain language request like "I want a vintage graphic tee under $30" and walks it through three tools to end with a shareable outfit caption. A search request triggers `search_listings`, which filters the mock dataset. If it finds a matching item, the top result triggers `suggest_outfit` to pair it with pieces already in the user's wardrobe, and that suggestion then triggers `create_fit_card` to write the final caption. When a tool comes up empty, such as `search_listings` returning no matches or the wardrobe being empty, the agent stops or falls back instead of passing junk forward, and it tells the user what went wrong and what to try next.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 0 (parse):** The agent creates the session and parses the query. It finds "$30" and sets `max_price = 30.0`, finds no explicit size token so leaves `size = None`, and keeps "vintage graphic tee" as the `description`. The mention of baggy jeans and chunky sneakers is not a search filter; it is already represented in the example wardrobe, so it is not parsed into the search.

**Step 1:** The agent calls `search_listings(description="vintage graphic tee", size=None, max_price=30.0)`. With no size filter and a $30 ceiling, the dataset narrows to the tee listings under $30, and keyword scoring on "vintage", "graphic", and "tee" ranks the band and graphic tees highest. The tool returns a non-empty list, and the loop stores it in `session["search_results"]`.

**Step 2:** The loop sees the list is not empty, so it sets `session["selected_item"] = search_results[0]`. For this query the implemented tool ranks the Y2K Baby Tee, Butterfly Print, $18, from depop (`lst_002`) as the top match, since it carries the "vintage", "graphic", and "tee" keywords. It then calls `suggest_outfit(new_item=<that baby tee>, wardrobe=<example wardrobe>)`. The tool sees the wardrobe has items, so it builds a styling prompt and returns something like "Pair the Y2K baby tee with your baggy straight-leg jeans and chunky white sneakers for a casual streetwear look. Tuck the front into the waistband to define the shape." This is stored in `session["outfit_suggestion"]`.

**Step 3:** The loop calls `create_fit_card(outfit=<that suggestion>, new_item=<baby tee>)`. Running at a higher temperature, the tool returns a casual caption that names the tee, its $18 price, and depop once each, for example "scored this Y2K baby tee on depop for $18 and it already lives in my jeans-and-sneakers rotation 🦋 cool girl vibes only." This is stored in `session["fit_card"]`, and `session["error"]` stays None.

**Final output to user:** The agent returns the session, and the caller shows the found item (Y2K Baby Tee, $18, depop), the outfit suggestion that pairs it with their baggy jeans and chunky sneakers, and the final fit card caption ready to post. If the search in Step 1 had returned nothing, the user would instead see only the error message from `session["error"]` explaining what to change, and Steps 2 and 3 would never run.
