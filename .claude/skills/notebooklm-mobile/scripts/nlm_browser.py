#!/usr/bin/env python3
"""
Browser-driven NotebookLM client.

Drives a real Chromium signed into your Google account via a persistent
profile at ~/.notebooklm/chrome-profile/. One interactive login on first
run; headless after that.

Commands:

  login              First-run interactive sign-in (always --visible).
  check-ui           Probe every selector in nlm_selectors.py and report.
  list-notebooks     Print id + title of every notebook on the home page.
  list-sources       Print sources in a notebook.
  add-url            Add a URL source.
  add-text           Add pasted text as a source.
  add-pdf            Upload a PDF file as a source.
  create-notebook    Create a new empty notebook with a given title.
  delete-source      Delete a source by title (requires --confirm).
  delete-notebook    Delete a notebook by id (requires --confirm).
  chat               Send a chat query and print the assistant response.
  open-on-phone      Emit the mobile deep link for a notebook.

Dependencies:
  pip install playwright
  playwright install chromium

See references/playwright_setup.md for first-run instructions.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator

try:
    from playwright.sync_api import (
        BrowserContext,
        Locator,
        Page,
        Playwright,
        TimeoutError as PWTimeout,
        sync_playwright,
    )
except ImportError:
    print(
        "Playwright is not installed. Run:\n"
        "  pip install playwright\n"
        "  playwright install chromium\n"
        "Then retry. See references/playwright_setup.md.",
        file=sys.stderr,
    )
    sys.exit(1)

import nlm_selectors as S

PROFILE_DIR = pathlib.Path.home() / ".notebooklm" / "chrome-profile"
DEBUG_DIR = pathlib.Path.home() / ".notebooklm" / "debug"
NAV_TIMEOUT_MS = 30_000
ACTION_TIMEOUT_MS = 15_000
CHAT_TIMEOUT_MS = 120_000


# ---------------------------------------------------------------------------
# Browser plumbing
# ---------------------------------------------------------------------------

@contextmanager
def browser(visible: bool) -> Iterator[tuple[BrowserContext, Page]]:
    """Yield a persistent-profile browser context and its first page."""
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    PROFILE_DIR.chmod(0o700)
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=not visible,
            viewport={"width": 1440, "height": 900},
            ignore_https_errors=False,
        )
        ctx.set_default_timeout(ACTION_TIMEOUT_MS)
        ctx.set_default_navigation_timeout(NAV_TIMEOUT_MS)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            yield ctx, page
        finally:
            ctx.close()


def save_debug(page: Page, label: str) -> pathlib.Path:
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    path = DEBUG_DIR / f"{ts}-{label}.png"
    try:
        page.screenshot(path=str(path), full_page=True)
    except Exception:
        pass
    return path


def ensure_signed_in(page: Page) -> None:
    page.goto(S.HOME_URL, wait_until="domcontentloaded")
    # If we hit the Google sign-in gate, bail with a clear message.
    if "accounts.google.com" in page.url or page.get_by_role("button", name=re.compile(r"sign in", re.I)).count() > 0:
        save_debug(page, "not-signed-in")
        raise RuntimeError(
            "Not signed in. Run:  python scripts/nlm_browser.py login"
        )
    # Wait for the notebook grid or the empty state to render.
    try:
        page.wait_for_load_state("networkidle", timeout=NAV_TIMEOUT_MS)
    except PWTimeout:
        pass


def goto_home(page: Page) -> None:
    page.goto(S.HOME_URL, wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle", timeout=NAV_TIMEOUT_MS)


def goto_notebook(page: Page, notebook_id: str) -> None:
    page.goto(f"https://notebooklm.google.com/notebook/{notebook_id}", wait_until="domcontentloaded")
    try:
        S.sources_panel(page).wait_for(timeout=NAV_TIMEOUT_MS)
    except PWTimeout:
        save_debug(page, f"notebook-{notebook_id}-load-failed")
        raise


def extract_notebook_id(href: str) -> str | None:
    m = S.NOTEBOOK_URL_RE.search(href)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_login(args: argparse.Namespace) -> int:
    # Login always runs visible; ignore --visible/--headless flags.
    print("Launching Chromium with dedicated profile. Sign in to Google, then close the window.", file=sys.stderr)
    with browser(visible=True) as (ctx, page):
        page.goto(S.HOME_URL)
        print("Browser open. Sign in, confirm you land on NotebookLM home, then close the browser window.", file=sys.stderr)
        # Wait until either the page URL settles on notebooklm.google.com or the user closes.
        try:
            while True:
                if ctx.pages == []:
                    break
                p = ctx.pages[0]
                if p.url.startswith("https://notebooklm.google.com"):
                    # Give the user a chance to close manually; poll.
                    time.sleep(2)
                    if ctx.pages == []:
                        break
                    continue
                time.sleep(1)
        except Exception:
            pass
    print(f"Profile saved to {PROFILE_DIR}.", file=sys.stderr)
    return 0


def cmd_check_ui(args: argparse.Namespace) -> int:
    results: list[dict] = []
    with browser(visible=args.visible) as (_ctx, page):
        ensure_signed_in(page)
        # Home probes
        goto_home(page)
        for label, fn, where in S.PROBES:
            if where != "home":
                continue
            try:
                count = fn(page).count()
                results.append({"probe": label, "where": where, "ok": count > 0, "count": count})
            except Exception as e:
                results.append({"probe": label, "where": where, "ok": False, "error": str(e)[:120]})

        # Notebook probes: use the first notebook, if any.
        first = S.notebook_cards(page).first
        if first.count() > 0:
            href = first.get_attribute("href") or ""
            nb_id = extract_notebook_id(href)
            if nb_id:
                goto_notebook(page, nb_id)
                for label, fn, where in S.PROBES:
                    if where != "notebook":
                        continue
                    try:
                        count = fn(page).count()
                        results.append({"probe": label, "where": where, "ok": count > 0, "count": count})
                    except Exception as e:
                        results.append({"probe": label, "where": where, "ok": False, "error": str(e)[:120]})
        else:
            results.append({"probe": "(notebook probes skipped: no notebooks on home)", "where": "notebook", "ok": False})

        if args.screenshot:
            save_debug(page, "check-ui-final")

    ok = all(r.get("ok") for r in results)
    print(json.dumps(results, indent=2))
    return 0 if ok else 1


def cmd_list_notebooks(args: argparse.Namespace) -> int:
    out = []
    with browser(visible=args.visible) as (_ctx, page):
        ensure_signed_in(page)
        goto_home(page)
        cards = S.notebook_cards(page)
        n = cards.count()
        for i in range(n):
            card = cards.nth(i)
            href = card.get_attribute("href") or ""
            nb_id = extract_notebook_id(href)
            title = (card.inner_text() or "").strip().splitlines()[0] if card.inner_text() else ""
            out.append({"id": nb_id, "title": title})
    print(json.dumps(out, indent=2) if args.json else "\n".join(f"{r['id']}\t{r['title']}" for r in out))
    return 0


def cmd_list_sources(args: argparse.Namespace) -> int:
    out = []
    with browser(visible=args.visible) as (_ctx, page):
        ensure_signed_in(page)
        goto_notebook(page, args.notebook)
        rows = S.source_rows(page)
        n = rows.count()
        for i in range(n):
            row = rows.nth(i)
            try:
                title = (S.source_title_in_row(row).inner_text() or "").strip()
            except Exception:
                title = (row.inner_text() or "").strip().splitlines()[0]
            out.append({"index": i, "title": title})
    print(json.dumps(out, indent=2) if args.json else "\n".join(f"{r['index']}\t{r['title']}" for r in out))
    return 0


def _open_add_source_dialog(page: Page) -> None:
    S.add_source_button(page).click()
    S.add_source_dialog(page).wait_for(timeout=ACTION_TIMEOUT_MS)


def cmd_add_url(args: argparse.Namespace) -> int:
    with browser(visible=args.visible) as (_ctx, page):
        ensure_signed_in(page)
        goto_notebook(page, args.notebook)
        _open_add_source_dialog(page)
        try:
            S.add_source_tab(page, "website").click()
        except Exception:
            # Some builds show URL input inline without a tab switch.
            pass
        S.add_source_url_input(page).fill(args.url)
        S.add_source_submit(page).click()
        # Wait for dialog to close and a new source row to appear.
        S.add_source_dialog(page).wait_for(state="hidden", timeout=ACTION_TIMEOUT_MS)
        print(f"Added URL source to notebook {args.notebook}: {args.url}")
    return 0


def cmd_add_text(args: argparse.Namespace) -> int:
    text = args.text if args.text else sys.stdin.read()
    if not text.strip():
        print("Empty text; nothing to add.", file=sys.stderr)
        return 2
    with browser(visible=args.visible) as (_ctx, page):
        ensure_signed_in(page)
        goto_notebook(page, args.notebook)
        _open_add_source_dialog(page)
        try:
            S.add_source_tab(page, "text").click()
        except Exception:
            pass
        S.add_source_text_input(page).fill(text)
        S.add_source_submit(page).click()
        S.add_source_dialog(page).wait_for(state="hidden", timeout=ACTION_TIMEOUT_MS)
        print(f"Added text source to notebook {args.notebook} ({len(text)} chars)")
    return 0


def cmd_add_pdf(args: argparse.Namespace) -> int:
    path = pathlib.Path(args.path).expanduser().resolve()
    if not path.exists():
        print(f"PDF not found: {path}", file=sys.stderr)
        return 2
    with browser(visible=args.visible) as (_ctx, page):
        ensure_signed_in(page)
        goto_notebook(page, args.notebook)
        _open_add_source_dialog(page)
        S.add_source_file_input(page).set_input_files(str(path))
        # Some flows auto-submit on file select; others need an explicit submit.
        try:
            S.add_source_submit(page).click(timeout=3000)
        except Exception:
            pass
        S.add_source_dialog(page).wait_for(state="hidden", timeout=ACTION_TIMEOUT_MS * 4)
        print(f"Uploaded PDF source to notebook {args.notebook}: {path.name}")
    return 0


def cmd_create_notebook(args: argparse.Namespace) -> int:
    with browser(visible=args.visible) as (_ctx, page):
        ensure_signed_in(page)
        goto_home(page)
        S.create_notebook_button(page).click()
        # Some builds prompt for title up front; others drop you into the notebook
        # with an inline rename. Try the prompt flow first.
        try:
            title_input = S.create_notebook_title_input(page)
            title_input.wait_for(timeout=5000)
            title_input.fill(args.title)
            S.create_notebook_confirm(page).click()
        except PWTimeout:
            pass
        # Wait for URL to become /notebook/<id>.
        page.wait_for_url(S.NOTEBOOK_URL_RE, timeout=NAV_TIMEOUT_MS)
        nb_id = extract_notebook_id(page.url)
        print(json.dumps({"id": nb_id, "title": args.title}, indent=2))
    return 0


def _find_source_row_by_title(page: Page, title: str) -> Locator | None:
    rows = S.source_rows(page)
    n = rows.count()
    for i in range(n):
        row = rows.nth(i)
        text = (row.inner_text() or "").strip()
        if title.lower() in text.lower():
            return row
    return None


def cmd_delete_source(args: argparse.Namespace) -> int:
    if not args.confirm:
        print("Refusing to delete without --confirm.", file=sys.stderr)
        return 2
    with browser(visible=args.visible) as (_ctx, page):
        ensure_signed_in(page)
        goto_notebook(page, args.notebook)
        row = _find_source_row_by_title(page, args.title)
        if not row:
            print(f"No source matched title {args.title!r}.", file=sys.stderr)
            return 1
        S.source_row_menu(row).click()
        S.source_row_delete_menuitem(page).click()
        try:
            S.confirm_delete_button(page).click(timeout=5000)
        except PWTimeout:
            pass
        print(f"Deleted source {args.title!r} from {args.notebook}")
    return 0


def cmd_delete_notebook(args: argparse.Namespace) -> int:
    if not args.confirm:
        print("Refusing to delete notebook without --confirm.", file=sys.stderr)
        return 2
    with browser(visible=args.visible) as (_ctx, page):
        ensure_signed_in(page)
        goto_notebook(page, args.notebook)
        S.notebook_settings_button(page).click()
        S.delete_notebook_menuitem(page).click()
        S.confirm_delete_button(page).click()
        page.wait_for_url(re.compile(r"notebooklm\.google\.com/?$"), timeout=NAV_TIMEOUT_MS)
        print(f"Deleted notebook {args.notebook}")
    return 0


def cmd_chat(args: argparse.Namespace) -> int:
    with browser(visible=args.visible) as (_ctx, page):
        ensure_signed_in(page)
        goto_notebook(page, args.notebook)
        before = S.chat_messages(page).count()
        S.chat_input(page).fill(args.question)
        S.chat_submit(page).click()
        # Wait for a new message bubble and for the loading indicator to disappear.
        deadline = time.time() + CHAT_TIMEOUT_MS / 1000
        answer_text = ""
        while time.time() < deadline:
            count = S.chat_messages(page).count()
            loading = False
            try:
                loading = S.chat_loading_indicator(page).count() > 0
            except Exception:
                pass
            if count > before and not loading:
                answer_text = (S.chat_messages(page).nth(count - 1).inner_text() or "").strip()
                if answer_text:
                    break
            time.sleep(0.5)
        if not answer_text:
            save_debug(page, "chat-timeout")
            print("Chat timed out or response not captured. See ~/.notebooklm/debug/.", file=sys.stderr)
            return 1
        print(answer_text)
    return 0


def cmd_open_on_phone(args: argparse.Namespace) -> int:
    # Pure URL formatting; reuse deeplink.py logic inline to avoid cross-import.
    https = f"https://notebooklm.google.com/notebook/{args.notebook}"
    intent = (
        f"intent://notebooklm.google.com/notebook/{args.notebook}"
        f"#Intent;scheme=https;action=android.intent.action.VIEW;"
        f"package=com.google.android.apps.labs.language.tailwind;end"
    )
    print(json.dumps({"https": https, "android_intent": intent}, indent=2))
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--visible", action="store_true", help="Run the browser visibly (default: headless).")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("login", help="Interactive first-run sign-in.").set_defaults(func=cmd_login)

    cu = sub.add_parser("check-ui", help="Probe selectors against the live UI.")
    cu.add_argument("--screenshot", action="store_true")
    cu.set_defaults(func=cmd_check_ui)

    ln = sub.add_parser("list-notebooks")
    ln.add_argument("--json", action="store_true")
    ln.set_defaults(func=cmd_list_notebooks)

    ls = sub.add_parser("list-sources")
    ls.add_argument("--notebook", required=True)
    ls.add_argument("--json", action="store_true")
    ls.set_defaults(func=cmd_list_sources)

    au = sub.add_parser("add-url")
    au.add_argument("--notebook", required=True)
    au.add_argument("--url", required=True)
    au.set_defaults(func=cmd_add_url)

    at = sub.add_parser("add-text")
    at.add_argument("--notebook", required=True)
    at.add_argument("--text", default=None, help="If omitted, read from stdin.")
    at.set_defaults(func=cmd_add_text)

    ap = sub.add_parser("add-pdf")
    ap.add_argument("--notebook", required=True)
    ap.add_argument("--path", required=True)
    ap.set_defaults(func=cmd_add_pdf)

    cn = sub.add_parser("create-notebook")
    cn.add_argument("--title", required=True)
    cn.set_defaults(func=cmd_create_notebook)

    ds = sub.add_parser("delete-source")
    ds.add_argument("--notebook", required=True)
    ds.add_argument("--title", required=True, help="Substring match, case-insensitive.")
    ds.add_argument("--confirm", action="store_true")
    ds.set_defaults(func=cmd_delete_source)

    dn = sub.add_parser("delete-notebook")
    dn.add_argument("--notebook", required=True)
    dn.add_argument("--confirm", action="store_true")
    dn.set_defaults(func=cmd_delete_notebook)

    ch = sub.add_parser("chat")
    ch.add_argument("--notebook", required=True)
    ch.add_argument("--question", required=True)
    ch.set_defaults(func=cmd_chat)

    op = sub.add_parser("open-on-phone")
    op.add_argument("--notebook", required=True)
    op.set_defaults(func=cmd_open_on_phone)

    return p


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
