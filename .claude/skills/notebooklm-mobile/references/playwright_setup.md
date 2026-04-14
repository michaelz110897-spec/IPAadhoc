# Playwright + first-run login

`scripts/nlm_browser.py` drives a real Chromium signed into your Google
account. One interactive login; headless thereafter.

## 1. Install

```bash
pip install playwright
playwright install chromium
```

Chromium installs into `~/.cache/ms-playwright/` (~200 MB).

## 2. Interactive login (one-time)

```bash
python .claude/skills/notebooklm-mobile/scripts/nlm_browser.py login
```

- A Chromium window opens at notebooklm.google.com.
- Sign in with the Google account you use for NotebookLM.
- Complete any 2FA / account-picker steps.
- When you land on the NotebookLM home page, close the window.

The session cookies are saved to `~/.notebooklm/chrome-profile/`. This
directory is 700 (user-only) and gitignored. Treat it like you would any
cookie jar.

## 3. Verify the skill can read your account

```bash
python scripts/nlm_browser.py list-notebooks
```

You should see one `<id>\t<title>` line per notebook. If you see nothing
but you know you have notebooks, run `check-ui --visible --screenshot`
-- selectors may need updating. See `selectors.md`.

## 4. Headless by default

After login, every command runs headless. Pass `--visible` before the
subcommand to watch:

```bash
python scripts/nlm_browser.py --visible list-sources --notebook <id>
```

## 5. Rotating or revoking access

- **Rotate**: delete `~/.notebooklm/chrome-profile/` and re-run `login`.
- **Revoke**: visit https://myaccount.google.com/permissions and sign
  out "Chromium" from the device list. Then also delete the profile dir
  locally so stale cookies don't linger.

## 6. When NOT to use this

- Shared machines. The profile dir has your Google session; anyone with
  read access to your home dir can lift it.
- CI / automation that runs unattended without your knowledge. This
  skill impersonates you; don't surprise yourself with it.
- Long-running loops. NotebookLM has no public API; aggressive
  automation can trigger anti-abuse flags on your account.

## 7. Relationship to HAR-replay (`nlm_client.py`)

The browser driver is the primary path for interactive work. The HAR
client remains as:

- A fallback when the UI is broken but the underlying RPC still works
  (rare but happens during A/B tests).
- A lighter option for pure scripted batch jobs where you don't need a
  browser running.

Most users can ignore `nlm_client.py` once `nlm_browser.py` works.
