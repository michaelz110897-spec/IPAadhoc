# Updating selectors when the NotebookLM UI changes

The browser driver's UI contract lives in **one file**:
`scripts/nlm_selectors.py`. When NotebookLM ships a redesign and the
skill starts failing, you patch that file -- no other code changes.

## Symptom → cause → fix

| Symptom | Likely cause | Fix |
|---|---|---|
| `check-ui` reports `notebook cards on home` count=0 | Home grid structure changed | Update `notebook_cards()` to match the new card element |
| `add-url` hangs at "click add source" | Button accessible name changed | Update `add_source_button()` regex |
| Chat responses never captured | Message container role/class changed | Update `chat_messages()` |
| All selectors fail | You're signed out, or hit an interstitial | Run `nlm_browser.py login` again |

## Playbook

1. Reproduce the failure with the visible browser and a screenshot:

   ```bash
   python scripts/nlm_browser.py --visible check-ui --screenshot
   ```

   Debug PNGs land in `~/.notebooklm/debug/`.

2. Open the failing page in your signed-in browser and launch Playwright
   codegen to record a working interaction:

   ```bash
   playwright codegen https://notebooklm.google.com
   ```

   Click through the action that's broken. Codegen prints the locators
   it would use. Prefer `get_by_role()` and `get_by_text()` in the
   generated snippet over brittle CSS class selectors.

3. Update the matching entry in `scripts/nlm_selectors.py`. Keep the
   function signature (`(page: Page) -> Locator`) intact so the driver
   doesn't need touching.

4. Re-run `check-ui`. Iterate until all probes return `"ok": true`.

## Selector style guide

Do:
- `page.get_by_role("button", name=re.compile(r"add source", re.I))`
- `page.get_by_label(...)`, `page.get_by_text(...)`, `page.get_by_placeholder(...)`
- Combine with `.filter(has=...)` and `.or_(...)` for resilience across
  A/B variants.

Avoid:
- CSS class selectors (`.someMaterialClass123`). NotebookLM uses hashed
  class names that churn on every deploy.
- XPath unless semantic lookups genuinely can't reach the element.
- `nth-child` positional selectors.

## When two variants coexist (A/B testing)

Google frequently ships NotebookLM behind A/B flags. Use `.or_(...)` to
accept either variant in one selector:

```python
def add_source_button(page):
    return page.get_by_role("button", name=re.compile(r"add source", re.I)).or_(
        page.get_by_role("button", name=re.compile(r"add material", re.I))
    ).first
```

The driver picks whichever branch is present and ignores the other.

## Keeping history

Before you edit `nlm_selectors.py`, skim `git log -- scripts/nlm_selectors.py`
-- if the same selector has churned multiple times, there's a pattern
worth preserving (maybe NotebookLM alternates between two names).
