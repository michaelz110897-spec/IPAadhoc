"""
NotebookLM UI selector map.

Every action in `nlm_browser.py` looks up its selectors here so the UI
contract is reviewable and patchable in one place. Prefer semantic
Playwright locators (get_by_role, get_by_label, get_by_text) over CSS
-- they survive CSS-class churn and most redesigns.

When selectors break:

  1. Run `python scripts/nlm_browser.py check-ui --visible` to see which
     selectors no longer match, with screenshots saved to
     ~/.notebooklm/debug/.
  2. Update the affected entry below.
  3. Re-run check-ui.
  4. See references/selectors.md for the full update playbook.

Each selector is a callable taking a Playwright Page/Locator and
returning a Locator. This indirection lets us use compound lookups
(role + name + ancestor chain) while keeping the map declarative.
"""

from __future__ import annotations

import re
from typing import Callable

from playwright.sync_api import Locator, Page

# URL patterns ---------------------------------------------------------------

HOME_URL = "https://notebooklm.google.com/"
NOTEBOOK_URL_RE = re.compile(r"notebooklm\.google\.com/notebook/([A-Za-z0-9\-_]+)")


# Home page: notebook grid ---------------------------------------------------

def notebook_cards(page: Page) -> Locator:
    """All notebook tiles on the home page.

    NotebookLM's home shows each notebook as a clickable card that
    navigates to /notebook/<id>. We match on role=link scoped to the
    main content area.
    """
    return page.get_by_role("main").get_by_role("link").filter(
        has=page.locator("[href*='/notebook/']")
    )


def create_notebook_button(page: Page) -> Locator:
    return page.get_by_role("button", name=re.compile(r"(new notebook|create)", re.I)).first


def create_notebook_title_input(page: Page) -> Locator:
    return page.get_by_role("textbox").first


def create_notebook_confirm(page: Page) -> Locator:
    return page.get_by_role("button", name=re.compile(r"^create$", re.I))


# Notebook page: sources panel -----------------------------------------------

def sources_panel(page: Page) -> Locator:
    return page.get_by_role("complementary", name=re.compile(r"sources", re.I)).or_(
        page.get_by_role("region", name=re.compile(r"sources", re.I))
    ).first


def source_rows(page: Page) -> Locator:
    """Individual source entries inside the sources panel."""
    return sources_panel(page).get_by_role("listitem").or_(
        sources_panel(page).locator("[role='row']")
    )


def source_title_in_row(row: Locator) -> Locator:
    return row.locator("[class*='title'], [class*='name']").first.or_(row.get_by_role("heading"))


def add_source_button(page: Page) -> Locator:
    return page.get_by_role("button", name=re.compile(r"add (source|material)", re.I)).first


# Add-source dialog ----------------------------------------------------------

def add_source_dialog(page: Page) -> Locator:
    return page.get_by_role("dialog")


def add_source_tab(page: Page, kind: str) -> Locator:
    """kind is 'website', 'text', or 'pdf' (case-insensitive)."""
    return add_source_dialog(page).get_by_role("tab", name=re.compile(kind, re.I)).or_(
        add_source_dialog(page).get_by_role("button", name=re.compile(kind, re.I))
    ).first


def add_source_url_input(page: Page) -> Locator:
    return add_source_dialog(page).get_by_role("textbox")


def add_source_text_input(page: Page) -> Locator:
    return add_source_dialog(page).get_by_role("textbox")


def add_source_file_input(page: Page) -> Locator:
    """File picker for PDF upload. Input[type=file] is usually hidden."""
    return add_source_dialog(page).locator("input[type='file']")


def add_source_submit(page: Page) -> Locator:
    return add_source_dialog(page).get_by_role("button", name=re.compile(r"(insert|add|upload|submit)", re.I))


# Source row actions (menu -> delete) ----------------------------------------

def source_row_menu(row: Locator) -> Locator:
    return row.get_by_role("button", name=re.compile(r"(more|options|menu)", re.I)).first


def source_row_delete_menuitem(page: Page) -> Locator:
    return page.get_by_role("menuitem", name=re.compile(r"(delete|remove)", re.I)).first


# Confirm dialog (shared by delete flows) ------------------------------------

def confirm_delete_button(page: Page) -> Locator:
    return page.get_by_role("dialog").get_by_role("button", name=re.compile(r"(delete|remove|confirm)", re.I)).first


# Chat panel -----------------------------------------------------------------

def chat_input(page: Page) -> Locator:
    return page.get_by_role("textbox", name=re.compile(r"(ask|message|chat|question)", re.I)).or_(
        page.get_by_placeholder(re.compile(r"(ask|message|type)", re.I))
    ).first


def chat_submit(page: Page) -> Locator:
    return page.get_by_role("button", name=re.compile(r"(send|submit|ask)", re.I)).first


def chat_messages(page: Page) -> Locator:
    """Assistant message bubbles in the chat transcript."""
    return page.get_by_role("article").or_(
        page.locator("[role='log'] [class*='message']")
    )


def chat_loading_indicator(page: Page) -> Locator:
    return page.get_by_role("progressbar").or_(page.locator("[class*='loading'], [class*='spinner']"))


# Notebook settings (rename / delete notebook) -------------------------------

def notebook_settings_button(page: Page) -> Locator:
    return page.get_by_role("button", name=re.compile(r"(settings|more|options)", re.I)).first


def delete_notebook_menuitem(page: Page) -> Locator:
    return page.get_by_role("menuitem", name=re.compile(r"delete notebook", re.I)).first


# check-ui probe list --------------------------------------------------------
# Each entry: (human label, selector fn, where to run it).
# "home" means run on the home page; "notebook" means from inside any notebook;
# "dialog" means a modal must be open first (skipped in plain check-ui).

PROBES: list[tuple[str, Callable[[Page], Locator], str]] = [
    ("notebook cards on home", notebook_cards, "home"),
    ("create-notebook button", create_notebook_button, "home"),
    ("sources panel", sources_panel, "notebook"),
    ("source rows", source_rows, "notebook"),
    ("add-source button", add_source_button, "notebook"),
    ("chat input", chat_input, "notebook"),
    ("chat submit", chat_submit, "notebook"),
    ("notebook settings button", notebook_settings_button, "notebook"),
]
