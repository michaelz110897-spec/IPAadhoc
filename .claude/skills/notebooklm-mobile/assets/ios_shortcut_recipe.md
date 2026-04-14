# iOS Shortcut: "Send to NotebookLM"

A one-time Shortcut install that lets Claude (or anything that can open a
URL on your phone) push content into NotebookLM via the iOS share sheet.

## Build steps

1. Open the **Shortcuts** app on your iPhone/iPad.
2. Tap `+` to create a new Shortcut. Name it **Send to NotebookLM**.
3. Add actions in this order:

   | # | Action | Configuration |
   |---|---|---|
   | 1 | **Receive input** (tap the shortcut's settings gear → *Share Sheet*) | Accept: **Text, URLs, Files** |
   | 2 | **Get Contents of URL** *(only if you want to resolve short URLs first — optional)* | Use Shortcut Input |
   | 3 | **Open App** | App: **NotebookLM** |
   | 4 | **Wait** | 1 second (gives the app time to foreground) |
   | 5 | **Share** | Input: Shortcut Input · Destination: **NotebookLM** |

4. Pin the shortcut to the share sheet (toggle *Show in Share Sheet* in the
   settings gear).

## Invoking from a URL

Once the shortcut exists, any app that can open a URL can invoke it:

```
shortcuts://run-shortcut?name=Send%20to%20NotebookLM&input=text&text=<URL-ENCODED-CONTENT>
```

Or with `x-callback-url` if you want a return trip:

```
shortcuts://x-callback-url/run-shortcut?name=Send%20to%20NotebookLM&input=text&text=<URL-ENCODED-CONTENT>&x-success=<RETURN-URL>
```

Tap the URL in a message/email/note on the iPhone and it will:

1. Launch the Shortcut with your text as input.
2. Open NotebookLM.
3. Share the text to NotebookLM, which adds it as a new source (you pick
   which notebook from the system share sheet that appears).

## Troubleshooting

- **"Cannot find shortcut"**: The shortcut name must match exactly. Case
  and whitespace matter. Rename the shortcut in the app if you changed the
  URL or vice versa.
- **Share sheet shows web upload instead of app**: Reinstall NotebookLM
  from the App Store, then toggle *Show in Share Sheet* on the Shortcut.
- **Large text silently dropped**: iOS caps URL length. For anything over
  ~2KB, write the content to a file (via the Files action) first and pass
  the file instead of raw text.

## Handing off a notebook directly

If you already know the notebook ID, skip the Shortcut entirely: open
`https://notebooklm.google.com/notebook/<id>` in Safari on iOS. The
Universal Link opens the NotebookLM app if installed.
