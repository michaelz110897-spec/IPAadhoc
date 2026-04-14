#!/usr/bin/env python3
"""
Unofficial NotebookLM client via HAR replay.

NotebookLM's web app talks to `notebooklm.google.com/_/*/data/batchexecute`
using Google's internal RPC format. RPC IDs and payload shapes change over
time, so this script does NOT hardcode them. Instead it:

  1. Reads a HAR file captured by the user while logged into NotebookLM and
     performing the action they want to automate (create notebook, add URL
     source, etc.).
  2. Extracts the matching request as a template.
  3. Rewrites placeholders (notebook id, source URL, title text) in the
     `f.req` payload.
  4. Regenerates the time-sensitive `SAPISIDHASH` Authorization header from
     the SAPISID cookie.
  5. Replays the request against live NotebookLM.

See references/auth_setup.md for how to capture the HAR, and
references/endpoints.md for notes on the RPCs.

Dependencies: stdlib only. The script calls out to `curl` for transport so
that users who don't want to pip-install requests can still use it. Use
`--transport requests` to use the Python requests library if installed.

SECURITY: The HAR contains full session cookies. Keep it out of git.
Default HAR path is ~/.notebooklm/session.har.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import time
from typing import Any
from urllib.parse import urlparse

DEFAULT_HAR = pathlib.Path.home() / ".notebooklm" / "session.har"
ORIGIN = "https://notebooklm.google.com"


# --- HAR parsing ------------------------------------------------------------

def load_har(path: pathlib.Path) -> list[dict[str, Any]]:
    with path.open() as f:
        har = json.load(f)
    return har["log"]["entries"]


def find_batchexecute_entries(entries: list[dict[str, Any]], rpc_marker: str | None = None) -> list[dict[str, Any]]:
    """Return HAR entries that look like batchexecute POSTs.

    rpc_marker: a substring that must appear in the request postData (e.g.
    the RPC ID, or a unique value like the notebook title you used during
    capture). This is how we pick the right entry without hardcoding IDs.
    """
    out = []
    for e in entries:
        req = e["request"]
        if req["method"] != "POST":
            continue
        url = req["url"]
        if "batchexecute" not in url:
            continue
        if rpc_marker is not None:
            body = (req.get("postData") or {}).get("text", "")
            if rpc_marker not in body and rpc_marker not in url:
                continue
        out.append(e)
    return out


def extract_template(entry: dict[str, Any]) -> dict[str, Any]:
    """Reduce a HAR entry to the minimum needed to replay."""
    req = entry["request"]
    headers = {h["name"]: h["value"] for h in req["headers"] if not h["name"].startswith(":")}
    # Strip hop-by-hop and auto-managed headers
    for bad in ("host", "content-length", "accept-encoding", "connection", "authorization"):
        headers.pop(bad, None)
        headers.pop(bad.title(), None)
    cookies = {c["name"]: c["value"] for c in req.get("cookies", [])}
    post = (req.get("postData") or {}).get("text", "")
    return {
        "url": req["url"],
        "headers": headers,
        "cookies": cookies,
        "body": post,
    }


# --- SAPISIDHASH ------------------------------------------------------------

def sapisidhash(sapisid: str, origin: str = ORIGIN, now: int | None = None) -> str:
    """Compute the `Authorization: SAPISIDHASH ...` value Google uses.

    hash = SHA1(f"{timestamp} {SAPISID} {origin}")
    header value = f"{timestamp}_{hash}"
    """
    now = now if now is not None else int(time.time())
    raw = f"{now} {sapisid} {origin}".encode()
    h = hashlib.sha1(raw).hexdigest()
    return f"{now}_{h}"


def cookie_header(cookies: dict[str, str]) -> str:
    return "; ".join(f"{k}={v}" for k, v in cookies.items())


# --- Payload substitution ---------------------------------------------------

def substitute(body: str, subs: dict[str, str]) -> str:
    """Apply text substitutions to the captured request body.

    This is intentionally a literal string replace -- the batchexecute
    body is URL-encoded JSON-in-a-string and it's safer to let the user
    specify exact markers than to try to parse and re-serialize.
    """
    out = body
    for needle, replacement in subs.items():
        if needle not in out:
            raise KeyError(f"Marker {needle!r} not found in captured body. Recapture the HAR with that exact marker, or fix the --sub flag.")
        out = out.replace(needle, replacement)
    return out


# --- Transport --------------------------------------------------------------

def replay_curl(template: dict[str, Any], body: str, auth: str) -> tuple[int, str]:
    args = ["curl", "-sS", "-X", "POST", template["url"]]
    for k, v in template["headers"].items():
        args += ["-H", f"{k}: {v}"]
    args += ["-H", f"Authorization: SAPISIDHASH {auth}"]
    args += ["-H", f"Cookie: {cookie_header(template['cookies'])}"]
    args += ["-H", f"Origin: {ORIGIN}"]
    args += ["--data-binary", body]
    args += ["-o", "-", "-w", "\n__HTTP_STATUS__:%{http_code}"]
    r = subprocess.run(args, capture_output=True, text=True)
    text = r.stdout
    status = 0
    if "__HTTP_STATUS__:" in text:
        text, tail = text.rsplit("__HTTP_STATUS__:", 1)
        status = int(tail.strip() or "0")
    if r.returncode != 0 and status == 0:
        text += f"\n[curl stderr]\n{r.stderr}"
    return status, text


def replay_requests(template: dict[str, Any], body: str, auth: str) -> tuple[int, str]:
    try:
        import requests  # type: ignore
    except ImportError:
        print("requests not installed; falling back to curl.", file=sys.stderr)
        return replay_curl(template, body, auth)
    headers = dict(template["headers"])
    headers["Authorization"] = f"SAPISIDHASH {auth}"
    headers["Cookie"] = cookie_header(template["cookies"])
    headers["Origin"] = ORIGIN
    r = requests.post(template["url"], headers=headers, data=body)
    return r.status_code, r.text


# --- Commands ---------------------------------------------------------------

def cmd_inspect(args: argparse.Namespace) -> int:
    entries = load_har(args.har)
    matches = find_batchexecute_entries(entries, rpc_marker=args.marker)
    if not matches:
        print(f"No batchexecute entries matched (marker={args.marker!r}).", file=sys.stderr)
        return 1
    for i, e in enumerate(matches):
        req = e["request"]
        started = e.get("startedDateTime", "?")
        url = urlparse(req["url"])
        body = (req.get("postData") or {}).get("text", "")
        snippet = body[:200].replace("\n", " ")
        print(f"[{i}] {started} {url.path}?{url.query[:80]}...")
        print(f"     body[:200]={snippet!r}")
    return 0


def cmd_replay(args: argparse.Namespace) -> int:
    entries = load_har(args.har)
    matches = find_batchexecute_entries(entries, rpc_marker=args.marker)
    if not matches:
        print(f"No batchexecute entries matched (marker={args.marker!r}).", file=sys.stderr)
        return 1
    if args.index >= len(matches):
        print(f"Only {len(matches)} matches; index {args.index} out of range.", file=sys.stderr)
        return 1
    template = extract_template(matches[args.index])

    sapisid = template["cookies"].get("SAPISID") or template["cookies"].get("__Secure-3PAPISID")
    if not sapisid:
        print("No SAPISID / __Secure-3PAPISID cookie in HAR. Recapture while logged in.", file=sys.stderr)
        return 1

    subs: dict[str, str] = {}
    for raw in args.sub or []:
        if "=" not in raw:
            print(f"--sub expects needle=replacement, got {raw!r}", file=sys.stderr)
            return 2
        needle, _, replacement = raw.partition("=")
        subs[needle] = replacement

    body = substitute(template["body"], subs)
    auth = sapisidhash(sapisid)

    if args.dry_run:
        print("URL:", template["url"])
        print("Auth:", f"SAPISIDHASH {auth}")
        print("Cookies:", list(template["cookies"].keys()))
        print("Body (after sub):")
        print(body)
        return 0

    transport = replay_requests if args.transport == "requests" else replay_curl
    status, text = transport(template, body, auth)
    print(f"HTTP {status}")
    print(text)
    return 0 if 200 <= status < 300 else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--har", type=pathlib.Path, default=DEFAULT_HAR,
                   help=f"Path to captured HAR (default: {DEFAULT_HAR})")
    sub = p.add_subparsers(dest="cmd", required=True)

    i = sub.add_parser("inspect", help="List batchexecute entries in the HAR")
    i.add_argument("--marker", default=None, help="Substring to filter by (e.g. RPC ID or a unique title you used during capture)")
    i.set_defaults(func=cmd_inspect)

    r = sub.add_parser("replay", help="Replay a captured batchexecute request with substitutions")
    r.add_argument("--marker", required=True, help="Substring that uniquely identifies the captured request")
    r.add_argument("--index", type=int, default=0, help="If multiple matches, which one (default 0)")
    r.add_argument("--sub", action="append", default=[], help="needle=replacement; repeatable. Example: --sub 'My Capture Title=New Title'")
    r.add_argument("--transport", choices=("curl", "requests"), default="curl")
    r.add_argument("--dry-run", action="store_true", help="Print the request instead of sending it")
    r.set_defaults(func=cmd_replay)

    return p


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    if not args.har.exists():
        print(f"HAR not found: {args.har}. See references/auth_setup.md.", file=sys.stderr)
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
