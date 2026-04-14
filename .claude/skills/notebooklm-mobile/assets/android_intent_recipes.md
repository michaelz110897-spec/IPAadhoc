# Android intent recipes for NotebookLM

Two entry points: **on-device** (tap an `intent://` URL from any app) and
**desktop-driven** (run `adb shell am start ...` against a tethered
device). Both use the same package name:

```
com.google.android.apps.labs.language.tailwind
```

If that package isn't installed on the device, check:

```bash
adb shell pm list packages | grep -i tailwind
```

Google has renamed the NotebookLM package before; update the recipes if
the grep returns a different id.

---

## 1. Open a specific notebook

### As an `intent://` URL (tap target)

```
intent://notebooklm.google.com/notebook/<NOTEBOOK_ID>#Intent;scheme=https;action=android.intent.action.VIEW;package=com.google.android.apps.labs.language.tailwind;end
```

Paste into a message/note on the phone and tap it. Works from Chrome,
Gmail, Keep, Messages, etc.

### As an ADB command (desktop)

```bash
adb shell am start \
  -a android.intent.action.VIEW \
  -d 'https://notebooklm.google.com/notebook/<NOTEBOOK_ID>' \
  com.google.android.apps.labs.language.tailwind
```

## 2. Share text/URL into NotebookLM as a new source

ADB only — `ACTION_SEND` has no tap-URL equivalent.

### Plain text

```bash
adb shell am start \
  -a android.intent.action.SEND \
  -t 'text/plain' \
  --es android.intent.extra.TEXT 'Paste of text to save as a NotebookLM source.' \
  com.google.android.apps.labs.language.tailwind
```

### URL (same action, semantically a URL)

```bash
adb shell am start \
  -a android.intent.action.SEND \
  -t 'text/plain' \
  --es android.intent.extra.TEXT 'https://example.com/article' \
  com.google.android.apps.labs.language.tailwind
```

### PDF file

First push the PDF to the device, then share it with a content URI.
NotebookLM's Android share target accepts `application/pdf`:

```bash
adb push ./paper.pdf /sdcard/Download/paper.pdf
adb shell am start \
  -a android.intent.action.SEND \
  -t 'application/pdf' \
  --eu android.intent.extra.STREAM file:///sdcard/Download/paper.pdf \
  com.google.android.apps.labs.language.tailwind
```

> **Note:** `file://` URIs are blocked on Android 7+ in some OEM builds.
> If the share fails, use Android's Storage Access Framework or a
> content:// URI provided by a FileProvider instead.

## 3. Jump into a notebook and start a chat query

NotebookLM's mobile app does not currently accept chat-prefill params
reliably. The deep link opens the notebook, but the cursor lands on the
sources panel, not the chat box. If you need prefill, use the share
recipe in (2) — NotebookLM ingests the text as a source, and you can
immediately ask a question about it.

## 4. Building commands programmatically

Use `scripts/android_intent.py` from this skill:

```bash
# Tap target
python scripts/android_intent.py --mode uri open-notebook --notebook <id>

# ADB command
python scripts/android_intent.py --mode adb open-notebook --notebook <id>
python scripts/android_intent.py share-text --text 'Hello NotebookLM'
python scripts/android_intent.py share-url --url 'https://example.com'
```

The script handles shell-quoting of special characters (`&`, spaces,
quotes) inside `--es` extras, which is the failure mode most people hit
when writing these by hand.
