#!/usr/bin/env python3
"""
Build NotebookLM mobile deep links.

These URLs are Universal Links on iOS and App Links on Android. Tapping
them opens the NotebookLM app at the given notebook if the app is
installed; otherwise they fall back to the web app.

Pure string building -- no network calls, safe to run freely.
"""

from __future__ import annotations

import argparse
import sys
from urllib.parse import quote, urlencode

BASE = "https://notebooklm.google.com"


def notebook_url(notebook_id: str, *, authuser: int | None = None, query: str | None = None) -> str:
    """Return the https:// deep link for a notebook.

    notebook_id: the UUID-ish segment from a NotebookLM URL
        (e.g. the `abc123...` in https://notebooklm.google.com/notebook/abc123).
    authuser:    optional Google multi-account index (0, 1, 2, ...).
    query:       optional chat prefill; appended as a fragment that some
                 NotebookLM builds pick up. Not guaranteed across versions.
    """
    if "/" in notebook_id or notebook_id.startswith("http"):
        raise ValueError("Pass the notebook ID, not a full URL. Strip the host and /notebook/ prefix.")

    params = {}
    if authuser is not None:
        params["authuser"] = str(authuser)

    url = f"{BASE}/notebook/{notebook_id}"
    if params:
        url += "?" + urlencode(params)
    if query:
        url += "#q=" + quote(query, safe="")
    return url


def home_url(*, authuser: int | None = None) -> str:
    """Deep link that opens the NotebookLM home (notebook list)."""
    params = {}
    if authuser is not None:
        params["authuser"] = str(authuser)
    return BASE + ("/?" + urlencode(params) if params else "/")


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    nb = sub.add_parser("notebook", help="Build a link to a specific notebook")
    nb.add_argument("--notebook", required=True, help="NotebookLM notebook ID")
    nb.add_argument("--authuser", type=int, default=None)
    nb.add_argument("--query", default=None, help="Optional chat prefill")

    hm = sub.add_parser("home", help="Build a link to the NotebookLM home")
    hm.add_argument("--authuser", type=int, default=None)

    args = p.parse_args(argv)

    if args.cmd == "notebook":
        print(notebook_url(args.notebook, authuser=args.authuser, query=args.query))
    elif args.cmd == "home":
        print(home_url(authuser=args.authuser))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
