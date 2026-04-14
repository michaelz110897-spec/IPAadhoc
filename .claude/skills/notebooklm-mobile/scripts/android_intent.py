#!/usr/bin/env python3
"""
Build Android intent URIs and `adb shell am start` commands for NotebookLM.

Two output modes:

  uri       Emit an `intent://...#Intent;...;end` URL. Tap from an Android
            browser/messaging app to force-open NotebookLM. Needed when a
            plain https link resolves to the web app instead of the installed
            app (varies by launcher and default-app settings).

  adb       Emit a fully-escaped `adb shell am start ...` command. Run from
            a desktop with ADB over USB/Wi-Fi to drive an attached device.

Subcommands:
  open-notebook   Open NotebookLM at a given notebook.
  share-text      Send text to NotebookLM's share receiver (new source).
  share-url       Send a URL to NotebookLM's share receiver (new source).

NOTE: The Android package name is `com.google.android.apps.labs.language.tailwind`.
Google has renamed NotebookLM-related packages in the past. If the app
doesn't launch, check `adb shell pm list packages | grep -i tailwind`.
"""

from __future__ import annotations

import argparse
import shlex
import sys

PACKAGE = "com.google.android.apps.labs.language.tailwind"
HOST = "notebooklm.google.com"


def _intent_uri(path: str, action: str = "android.intent.action.VIEW") -> str:
    """Build an intent:// URL that force-opens the NotebookLM package."""
    return (
        f"intent://{HOST}{path}"
        f"#Intent;scheme=https;action={action};package={PACKAGE};end"
    )


def notebook_intent_uri(notebook_id: str) -> str:
    return _intent_uri(f"/notebook/{notebook_id}")


def adb_open_notebook(notebook_id: str) -> str:
    url = f"https://{HOST}/notebook/{notebook_id}"
    parts = [
        "adb", "shell", "am", "start",
        "-a", "android.intent.action.VIEW",
        "-d", url,
        PACKAGE,
    ]
    return " ".join(shlex.quote(p) for p in parts)


def adb_share_text(text: str) -> str:
    """Invoke the system share sheet with plain text, pre-targeted at NotebookLM."""
    parts = [
        "adb", "shell", "am", "start",
        "-a", "android.intent.action.SEND",
        "-t", "text/plain",
        "--es", "android.intent.extra.TEXT", text,
        PACKAGE,
    ]
    return " ".join(shlex.quote(p) for p in parts)


def adb_share_url(url: str) -> str:
    """Same as share_text but semantically a URL. NotebookLM treats both identically."""
    return adb_share_text(url)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--mode", choices=("uri", "adb"), default="adb",
                   help="Emit an intent:// URI (tap target) or adb shell command (default: adb).")
    sub = p.add_subparsers(dest="cmd", required=True)

    n = sub.add_parser("open-notebook")
    n.add_argument("--notebook", required=True)

    t = sub.add_parser("share-text")
    t.add_argument("--text", required=True)

    u = sub.add_parser("share-url")
    u.add_argument("--url", required=True)

    args = p.parse_args(argv)

    if args.cmd == "open-notebook":
        if args.mode == "uri":
            print(notebook_intent_uri(args.notebook))
        else:
            print(adb_open_notebook(args.notebook))
    elif args.cmd == "share-text":
        if args.mode == "uri":
            # intent:// form for ACTION_SEND is not a tap-target; fall back to adb.
            print("# 'share-text' has no tap-URL form; use --mode adb.", file=sys.stderr)
            return 2
        print(adb_share_text(args.text))
    elif args.cmd == "share-url":
        if args.mode == "uri":
            print("# 'share-url' has no tap-URL form; use --mode adb.", file=sys.stderr)
            return 2
        print(adb_share_url(args.url))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
