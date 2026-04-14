---
name: notebooklm-mobile
description: Push sources (URLs, text, files) to Google NotebookLM and produce mobile deep links or Shortcut/intent recipes that open the notebook on iOS/Android. Use when the user wants to hand content from this session off to NotebookLM on their phone, create or populate a notebook from conversation context, or generate a Shortcut/Android intent for NotebookLM ingestion. Android is the primary target; iOS is also supported.
---

# NotebookLM Mobile Integration

NotebookLM has **no public API**. This skill integrates with it via three layered approaches, from most to least stable:

1. **Mobile deep links** (stable). `https://notebooklm.google.com/notebook/{id}` is a Universal Link on iOS and an App Link on Android. Tapping it opens the NotebookLM app directly on the given notebook.
2. **Share-target intents** (stable). The NotebookLM mobile apps register as share receivers for `text/plain` and `application/pdf`. From Claude (desktop) we emit ready-to-run `am start` commands for ADB, and `shortcuts://` URLs for iOS. From the phone, the user taps and the app opens pre-filled.
3. **Unofficial scripted API** (fragile). NotebookLM's web app uses Google's `batchexecute` RPC. RPC IDs change periodically, so this skill does not hardcode them. Instead, `scripts/nlm_client.py` replays **HAR-captured** requests against the user's session. See `references/auth_setup.md` to capture your own.

## When to use this skill

Invoke this skill when the user asks to:

- "Send this to NotebookLM" / "Add this to my notebook"
- "Open NotebookLM on my phone at notebook X"
- "Make a Shortcut for NotebookLM"
- "Push these URLs into a new NotebookLM notebook"

If the user only wants to *summarize* content (no handoff to NotebookLM), do not invoke this skill.

## Workflow

Pick the branch that matches what the user needs. Do not run every script.

### Branch A — User has a phone in hand, wants a tap-to-open link

1. Ask which notebook (URL or ID). If they don't have one, offer to create one (Branch C).
2. Run `python scripts/deeplink.py --notebook <id> [--query "..."]`. Output is a short URL.
3. Paste the URL. On iOS it opens via Universal Link; on Android via App Link. Include both the `https://` form and the Android `intent://` form — some launchers need the intent form to force the app.

### Branch B — User wants a reusable Shortcut / intent recipe

1. Read `assets/android_intent_recipes.md` for ADB `am start` patterns and `intent://` URIs. Emit the specific command for their content.
2. For iOS, read `assets/ios_shortcut_recipe.md` and guide the user through building the one-time Shortcut. After it exists, emit `shortcuts://run-shortcut?name=...&input=...` URLs.
3. The package name is `com.google.android.apps.labs.language.tailwind` — this is hardcoded in the recipes. If the user reports "app not found," have them confirm via `adb shell pm list packages | grep tailwind` — Google has renamed the package before.

### Branch C — User wants to upload sources via script (desktop)

1. Confirm the user has completed `references/auth_setup.md` (captured a HAR while logged in). If not, walk them through it.
2. Use `scripts/nlm_client.py` with their HAR file and content:
   ```
   python scripts/nlm_client.py add-source \
     --har ~/.notebooklm/session.har \
     --notebook <id> \
     --url https://example.com/article
   ```
3. After upload, emit the mobile deep link (Branch A) so they can open the notebook on their phone.
4. If the HAR-replay fails with a 4xx, the RPC signature has drifted. Tell the user to recapture the HAR — do **not** guess at the new parameters.

### Branch D — User wants to create a new notebook from scratch

1. Gather the sources (URLs, pasted text, file paths). Summarize what will be ingested before acting.
2. Create the notebook via `scripts/nlm_client.py create-notebook --har ... --title "..."`. This returns a notebook ID.
3. Add each source (loop Branch C step 2).
4. Emit the mobile deep link.

## Invariants

- **Never** store session cookies in the repo. The HAR file lives in `~/.notebooklm/` (gitignored by this skill's own `.gitignore`).
- **Never** fabricate RPC IDs or endpoint paths. If a script fails, surface the HTTP response and ask the user to recapture.
- **Never** run `scripts/nlm_client.py` without confirming the user authorized the action — it mutates their NotebookLM account.
- Deep-link builders (`deeplink.py`, `android_intent.py`) are pure string formatters with no network calls — safe to run freely.
- When emitting Android ADB commands, quote `--es` extras carefully; URLs with `&` break unquoted `am start` commands.

## File map

| Path | Purpose | Read when |
| --- | --- | --- |
| `scripts/deeplink.py` | Build `https://notebooklm.google.com/...` URLs | Branch A |
| `scripts/android_intent.py` | Build `intent://` URIs and `am start` commands | Branch B (Android) |
| `scripts/nlm_client.py` | HAR-replay client for create-notebook / add-source | Branch C, D |
| `assets/ios_shortcut_recipe.md` | Step-by-step iOS Shortcut build | Branch B (iOS) |
| `assets/android_intent_recipes.md` | Share-intent patterns for Android | Branch B (Android) |
| `references/auth_setup.md` | How to capture a NotebookLM session HAR | Branch C, D (first run only) |
| `references/endpoints.md` | Known batchexecute RPC surface, with caveats | When scripted API breaks |

Load reference files only when the branch you're on requires them.
