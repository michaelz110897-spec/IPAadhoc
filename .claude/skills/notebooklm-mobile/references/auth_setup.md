# Capturing a NotebookLM session HAR

`scripts/nlm_client.py` replays captured requests. You need one HAR per
RPC you want to automate (create-notebook, add-source, etc.). The HAR
contains your full session cookies — **never commit it**.

## 1. Pick a capture directory

```bash
mkdir -p ~/.notebooklm
chmod 700 ~/.notebooklm
```

`scripts/nlm_client.py` defaults to `~/.notebooklm/session.har`.

## 2. Open DevTools with recording on

In a desktop Chrome profile that is signed into the Google account you
use for NotebookLM:

1. Navigate to https://notebooklm.google.com
2. Open **DevTools → Network**.
3. Toggle **Preserve log** on.
4. Clear the current log (🚫 icon) so the capture is minimal.

## 3. Perform the action you want to replay

For each RPC, do **exactly one** operation so the HAR is easy to filter,
and include a **unique string marker** you can grep for:

| RPC to capture | Action in the UI | Recommended marker |
|---|---|---|
| create-notebook | Click "New Notebook", title it `NLM-CAPTURE-CREATE-20260414` | `NLM-CAPTURE-CREATE-20260414` |
| add-source (URL) | In any notebook, Add source → Website → paste `https://example.com/nlm-capture-url-20260414` | `nlm-capture-url-20260414` |
| add-source (text) | Add source → Copied text → paste `NLM-CAPTURE-TEXT-20260414 ...` | `NLM-CAPTURE-TEXT-20260414` |

The marker must be unique enough that it only appears in the one request
you care about. Timestamped strings work well.

## 4. Export the HAR

Right-click anywhere in the Network panel → **Save all as HAR with
content** → save to `~/.notebooklm/session.har` (or a per-RPC path like
`~/.notebooklm/add-source.har`).

## 5. Verify the capture

```bash
python scripts/nlm_client.py --har ~/.notebooklm/session.har inspect --marker NLM-CAPTURE-CREATE-20260414
```

You should see exactly one `batchexecute` entry. If you see zero, your
marker didn't land in the body — recapture with a different UI flow
(sometimes the title is sent separately from the create RPC). If you see
many, tighten the marker.

## 6. Replay with substitutions

```bash
python scripts/nlm_client.py --har ~/.notebooklm/session.har replay \
  --marker NLM-CAPTURE-CREATE-20260414 \
  --sub 'NLM-CAPTURE-CREATE-20260414=My new notebook from Claude' \
  --dry-run
```

Inspect the dry-run output. If the URL, headers, and body look right,
drop `--dry-run` to actually POST.

## 7. Cookie lifetime

Google session cookies typically last weeks, but `SAPISID` in particular
can rotate on re-auth. If replays start returning 401/403, recapture —
don't try to refresh cookies by hand.

## Security checklist

- `~/.notebooklm/` is 700, user-only.
- The HAR is not symlinked into any git-tracked directory.
- Do not paste HAR contents into chat, commits, or issues.
- Revoke via https://myaccount.google.com/permissions if the file leaks.
