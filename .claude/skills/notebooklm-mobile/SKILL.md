---
name: notebooklm-mobile
description: Read from and act on Google NotebookLM through the user's Google account, and produce mobile deep links / Shortcut / Android intent recipes that hand off to the NotebookLM app. Use when the user wants to list or manage NotebookLM notebooks and sources from the terminal, chat with a notebook, add URL / text / PDF sources, create or delete notebooks, or open a notebook on their phone. Android is the primary mobile target; iOS is also supported.
---

# NotebookLM Integration (desktop + mobile)

NotebookLM has **no public API and no OAuth scope**. This skill integrates via four layered approaches, from most stable to least:

1. **Mobile deep links** (stable). `https://notebooklm.google.com/notebook/{id}` is a Universal Link on iOS and an App Link on Android. Pure URL formatting, no auth.
2. **Share-target intents** (stable). NotebookLM's mobile apps register as share receivers. We emit ADB `am start` commands and `intent://` URIs for Android, and Shortcut-compatible URLs for iOS.
3. **Browser automation** (preferred for "act on my account" use cases). `scripts/nlm_browser.py` drives a real Chromium using a persistent profile at `~/.notebooklm/chrome-profile/`. One interactive login; headless after that. Supports full CRUD + chat.
4. **Unofficial scripted API / HAR replay** (lightest, most fragile). `scripts/nlm_client.py` replays HAR-captured batchexecute requests. Useful when the UI breaks or when a browser is unavailable.

## When to use this skill

Invoke when the user asks to:

- "List / read my notebooks / sources"
- "Add this to my NotebookLM" / "Create a notebook with these sources"
- "Ask my notebook X about Y" (chat query)
- "Delete this source / notebook"
- "Open NotebookLM on my phone at notebook X"
- "Make a Shortcut / intent for NotebookLM"

If the user only wants to *summarize* content without touching their NotebookLM account, do not invoke.

## Workflow

Pick the branch that matches the user's ask. Do not run every script.

### Branch A — Mobile tap-to-open link

1. Get the notebook id (from a URL they paste, or Branch E's `list-notebooks`).
2. `python scripts/deeplink.py notebook --notebook <id>` → https:// Universal/App Link.
3. `python scripts/android_intent.py --mode uri open-notebook --notebook <id>` → intent:// URI for Android launchers that don't auto-route.

### Branch B — Reusable Shortcut / intent recipe

1. Android: consult `assets/android_intent_recipes.md` and emit the specific `adb shell am start ...` or `intent://` URL.
2. iOS: walk through `assets/ios_shortcut_recipe.md` once; afterward emit `shortcuts://run-shortcut?name=...&input=...` URLs.
3. Android package is `com.google.android.apps.labs.language.tailwind`. Verify with `adb shell pm list packages | grep tailwind` if it fails.

### Branch C — Read/act on the user's NotebookLM account (PREFERRED)

Use `scripts/nlm_browser.py` (Playwright). First run requires interactive login:

```
python scripts/nlm_browser.py login     # one time, visible
```

Then headless operation for everything else:

| Operation | Command |
| --- | --- |
| List notebooks | `nlm_browser.py list-notebooks` |
| List sources in a notebook | `nlm_browser.py list-sources --notebook <id>` |
| Add URL source | `nlm_browser.py add-url --notebook <id> --url <url>` |
| Add text source | `nlm_browser.py add-text --notebook <id> --text "..."` |
| Add PDF source | `nlm_browser.py add-pdf --notebook <id> --path ./file.pdf` |
| Create notebook | `nlm_browser.py create-notebook --title "..."` |
| Delete source | `nlm_browser.py delete-source --notebook <id> --title "..." --confirm` |
| Delete notebook | `nlm_browser.py delete-notebook --notebook <id> --confirm` |
| Chat with notebook | `nlm_browser.py chat --notebook <id> --question "..."` |
| Mobile handoff | `nlm_browser.py open-on-phone --notebook <id>` |

Pass `--visible` before any subcommand to watch the browser. Destructive operations (delete-*) require `--confirm`.

If a command hangs or returns empty, run `nlm_browser.py --visible check-ui --screenshot` — this probes each selector and writes screenshots to `~/.notebooklm/debug/`. Update `scripts/nlm_selectors.py` per `references/selectors.md` if probes fail.

### Branch D — Scripted API fallback (HAR replay)

Use when the browser path is unavailable (no Chromium) or a UI bug blocks browser automation:

1. Walk the user through `references/auth_setup.md` to capture a HAR.
2. `python scripts/nlm_client.py inspect --marker <unique>` then `replay --sub <needle>=<value>`.
3. If HAR replay fails with 4xx, recapture the HAR — do **not** guess RPC IDs.

### Branch E — User wants mobile handoff after desktop action

Chain: Branch C creates/populates a notebook → capture the returned id → Branch A emits the tap link. `open-on-phone` does this in one step.

## Invariants

- **No OAuth exists for NotebookLM.** Do not claim or attempt to build one.
- **Never** commit anything under `~/.notebooklm/`. `.gitignore` already excludes it, but re-check when adding new artifacts.
- **Always** require `--confirm` for destructive operations (delete-source, delete-notebook). Before invoking them, echo back the target title/id to the user and wait for explicit yes.
- **Never** fabricate RPC IDs or CSS classes. When the browser driver fails, direct the user to `check-ui` and the selector playbook rather than guessing.
- Deep-link builders are pure string formatters with no network calls — safe to run freely.
- The dedicated Chrome profile has full access to the signed-in Google account. Never copy, archive, or transmit the profile directory.
- When emitting Android ADB commands, rely on `android_intent.py`'s shell-quoting; don't hand-format `--es` extras.

## File map

| Path | Purpose | Read when |
| --- | --- | --- |
| `scripts/deeplink.py` | Build mobile deep-link URLs | Branch A |
| `scripts/android_intent.py` | Build `intent://` URIs + `am start` commands | Branch B (Android) |
| `scripts/nlm_browser.py` | Playwright CRUD + chat driver | **Branch C (primary)** |
| `scripts/nlm_selectors.py` | Centralized UI selector map | When check-ui reports failures |
| `scripts/nlm_client.py` | HAR-replay fallback | Branch D |
| `assets/ios_shortcut_recipe.md` | iOS Shortcut build steps | Branch B (iOS) |
| `assets/android_intent_recipes.md` | Android intent patterns | Branch B (Android) |
| `references/playwright_setup.md` | Install + first-run login | Branch C (first time) |
| `references/selectors.md` | Playbook for updating selectors | When browser UI breaks |
| `references/auth_setup.md` | HAR capture instructions | Branch D (first time) |
| `references/endpoints.md` | batchexecute RPC surface notes | When HAR replay breaks |

Load reference files only when the branch requires them.
