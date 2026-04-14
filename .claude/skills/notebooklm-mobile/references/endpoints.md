# NotebookLM endpoint notes

**Status: unofficial. Reverse-engineered from the web client. Will break.**

NotebookLM shares Google's generic "batchexecute" RPC transport with
Docs, Drive, Keep, etc. The surface as observed in early 2026:

- Origin: `https://notebooklm.google.com`
- RPC endpoint: `https://notebooklm.google.com/_/LabsTailwindUi/data/batchexecute`
  - The `_/LabsTailwindUi/` segment has changed at least once. If your
    HAR shows a different path (e.g. a new codename), use whatever the
    HAR says — `scripts/nlm_client.py` reads the URL from the capture.
- Query params include `rpcids=<comma-separated>`, `f.sid=`, `bl=`,
  `hl=`, `_reqid=`. Treat them all as opaque and replay verbatim.
- Body is `application/x-www-form-urlencoded`, keyed primarily by
  `f.req`. `f.req` is a URL-encoded JSON array of `[rpcid, args_json,
  null, "generic"]` tuples.

## Auth

- Cookies: `SAPISID` (or `__Secure-3PAPISID`), `SID`, `HSID`, `SSID`,
  `APISID`, `__Secure-1PSID`, `__Secure-3PSID`, and session helpers.
- Header: `Authorization: SAPISIDHASH <timestamp>_<sha1>` where the
  SHA-1 is computed over `"<timestamp> <SAPISID> https://notebooklm.google.com"`.
- The `Origin` request header must match what the hash was computed
  over. `nlm_client.py` hardcodes `https://notebooklm.google.com`.

## Known RPC categories

These IDs **will** change. Capture your own via HAR rather than trusting
this table — it exists only to orient you when reading a capture.

| Category | Typical payload shape in `f.req` |
|---|---|
| Create notebook | `[[[ "<rpcid>", "[\"<title>\"]", null, "generic" ]]]` |
| Add source (URL) | `[[[ "<rpcid>", "[[\"<url>\"]]", null, "generic" ]]]` |
| Add source (text) | `[[[ "<rpcid>", "[[\"<text>\"]]", null, "generic" ]]]` |
| List notebooks | `[[[ "<rpcid>", "[]", null, "generic" ]]]` |
| Delete notebook | `[[[ "<rpcid>", "[\"<notebook_id>\"]", null, "generic" ]]]` |

Response bodies start with the `)]}'` XSSI prefix followed by
length-prefixed JSON chunks. The current `nlm_client.py` returns the
raw text — caller can parse.

## Rate limits

No documented limits. Observed throttling kicks in around 10–20 rapid
source adds; back off to ~1/second if you're batching.

## When replays break

1. Recapture the HAR. Most breakage is from rotated RPC IDs or added
   required params; a fresh capture solves it without any code change.
2. If the new HAR's `f.req` shape has diverged (e.g. an extra arg
   appears that wasn't there before), update your `--sub` markers
   accordingly; don't try to derive the shape from docs.
3. If the endpoint path itself changed, the HAR URL will reflect it and
   `nlm_client.py` will pick it up automatically.

## Why we don't hardcode this

Every project that hardcodes NotebookLM RPC IDs ends up stale within
weeks. HAR replay trades a one-time capture step for a stable
integration that only breaks when Google changes the auth surface
itself, which is much rarer.
