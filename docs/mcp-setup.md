# Let a desktop chat app run the counts (optional, advanced)

This page is optional. It is for people who want Claude Desktop or the
ChatGPT desktop app to run the tool for them, instead of running the
commands themselves. Product facts were checked on 2026-11-01. These
products change often, so check the product's own docs before you rely on
a detail. Lines marked **Unverified** were not confirmed in the product's
docs or were not tested.

If you would rather run the tool yourself, use
[quick-start.md](quick-start.md). For assistants that run commands on
your computer (Claude Code, Codex, Copilot), use
[assistant-setup.md](assistant-setup.md) instead.

## What it is

`swlc_mcp.py`, in the repo root, is a small local server that a chat app
starts on your computer. It speaks MCP (Model Context Protocol), the
standard way chat apps add tools. It uses only the Python standard
library, makes no network requests and never runs `refresh_data.py`.

It gives the chat app exactly two tools:

- `preflight`: says whether the tool can use your inventory CSV. It
  returns only numbers, true/false values and fixed codes. It does not
  return your column titles (the `preflight` command in a terminal does).
- `check_counts`: runs the check with `--counts-only` and returns only the
  summary counts: `checked_on`, `kev_current`, `items`, `states`,
  `classification`, `ambiguous_review`, `support_records`, `count_total`
  and one count for each list. It never returns item IDs, names,
  versions, publishers or owners. The full report is written to a folder
  next to your CSV named after it: for `inventory.csv`, the folder is
  `swlc-out-inventory`. When the file name has unusual characters or is
  long, the folder name also ends in a short code made from the name (for
  `my file.csv`, something like `swlc-out-my_file-1a2b3c4d`), so two files
  never share a folder. The result tells the app where that folder is.
  Running it again on the same file replaces that file's report.

Each tool takes one thing: the full path to your inventory `.csv` file.
The server takes no other options, so the app cannot pass extra flags.

## What it protects, and what it does not

The rules are in the server's code, not in a prompt:

- What goes back to the app is rebuilt from fixed labels and numbers.
  Any line it does not expect is dropped. Nothing taken from your file
  reaches the app: no cell text, no column titles, no item IDs.
- It accepts only a full path to a file ending in `.csv` that is a
  regular file of at most 268435456 bytes (256 MiB, the tool's own limit).
  It refuses a path whose file itself is a symlink; a symlinked parent
  folder is followed (on macOS, `/tmp` is one). It refuses folders,
  devices, paths with control characters and paths longer than 4096
  characters. It checks the file name before it looks at the disk, and a
  missing file gets the same message as an unusable one, so the message
  does not say whether a file exists.
- Errors are short fixed messages with the exit code. The tool's own
  error text is never passed on.

What it does **not** protect:

- The counts, and the path you type, still go to the company that runs
  the chat app (Anthropic or OpenAI).
- Other tools in the same app can still read files. A file tool or
  another MCP server you have added could open your inventory or the
  report if the assistant chose to. Turn off file tools you do not need
  while you use this.
- Do not attach, upload or paste your inventory or a report into the
  chat. The server cannot stop that.
- The full report, with every name, is written next to your CSV. If that
  folder syncs to iCloud, OneDrive, Dropbox or a shared drive, the report
  goes to that service too. Running the check again on the same file
  replaces the old report.
- The assistant chooses the path, so it chooses where the report folder
  lands: next to any `.csv` file your user account can read, which may
  be in a synced or shared folder. Use the app's approval prompt to see
  the path before each run.
- Someone who can change files on your computer while a check runs is
  out of scope. The server opens the file once and checks it is the same
  file it checked, but the tool opens it again by name afterwards.
- One request is handled at a time. A check can take up to 280 seconds,
  and the server does not answer other messages during that time.
- Rows on your lists are not returned, only counts. To see which items
  are on a list, open `report.md` in the report folder yourself.

The fix codes `preflight` can return:

| Code | Meaning |
|---|---|
| `NO_ROWS` | Must fix. The file has a header row but no data rows. |
| `NO_NAME` | Must fix. No name column was found. |
| `NO_VERSION` | Must fix. No version column was found. |
| `NO_PUBLISHER` | No publisher column was found. |
| `NO_OWNER` | No owner column was found; every item will be listed as ownerless. |
| `NO_COUNT` | No count column was found. That is fine. |
| `NO_EXPORT_EOL` | No end-of-life date column was found. That is fine. |
| `NO_PARENT` | No parent column was found. That is fine. |
| `BLANK_NAME` | Some rows have a blank name cell. |
| `BLANK_VERSION` | Some rows have a blank version cell. |
| `BLANK_OWNER` | Some rows have a blank owner cell. |
| `UNREADABLE_DATE` | Some end-of-life date cells are not in YYYY-MM-DD form. |
| `PLACEHOLDER` | Some Parent cells hold a placeholder such as n/a. |
| `FORMULA` | Some cells start like a spreadsheet formula (=, +, -, @). |
| `OTHER_PROFILE` | Another profile fits the file better. |

Run `python3 software_lifecycle.py preflight` on the file in a terminal
for the full advice.

## Before you start

1. Check that Python 3.9 or newer is installed: `python3 --version` (on
   Windows, `py --version`). Install nothing else.
2. Download or clone the repo into a folder, for example
   `~/tools/software-lifecycle`.
3. Keep your inventory outside that folder, for example
   `~/inventories/inventory.csv`. The report folder will be
   `~/inventories/swlc-out-inventory`.
4. Test the server by hand. From the repo folder, run
   `python3 swlc_mcp.py` (on Windows, `py -3 swlc_mcp.py`). It prints one
   line starting with `swlc_mcp: started` and waits. Press Ctrl+C (on
   Windows, Ctrl+Z then Enter) to stop it.

In the settings below, replace `/path/to/software-lifecycle` with the full
path of your repo folder. On Windows, use the command `py`, the
arguments `-3` and the path, and write each backslash in a path twice in
JSON (`C:\\tools\\software-lifecycle\\swlc_mcp.py`).

## ChatGPT desktop app

Source: <https://learn.chatgpt.com/docs/extend/mcp?surface=desktop>
(no last-updated date shown). Not tested with this server:
**Unverified**.

In the app:

1. Open **Settings**, then select **MCP servers**.
2. Select **Add server**.
3. Enter a name (for example `software-lifecycle`), choose **STDIO**, and
   give the command `python3` with the argument
   `/path/to/software-lifecycle/swlc_mcp.py`.
4. Save the server, then select **Restart**.

Or add it to `~/.codex/config.toml`, which the desktop app, the Codex CLI
and the IDE extension share. These key names are from OpenAI's page:

```toml
[mcp_servers.software-lifecycle]
command = "python3"
args = ["/path/to/software-lifecycle/swlc_mcp.py"]
enabled_tools = ["preflight", "check_counts"]
default_tools_approval_mode = "prompt"
tool_timeout_sec = 300
```

- `enabled_tools` is an allow list: only these two tools are turned on.
- `default_tools_approval_mode = "prompt"` asks you before each tool call,
  so you see the path before it runs. OpenAI's page lists the values
  `auto`, `prompt`, `writes` and `approve`.
- `tool_timeout_sec` defaults to 60 seconds. A large inventory can take
  longer; the server itself stops a run after 280 seconds.

Approval settings in the app's own screens: not found on that page, so
they appear to be set in `config.toml` only. **Unverified**.

## Claude Desktop

The one-click package for Claude Desktop (a `.mcpb` file) is **not built
yet** and is untested. Whether Claude Desktop can find a Python already
installed on your computer for such a package is not confirmed.

A manual route is documented for local servers in general:
<https://modelcontextprotocol.io/docs/develop/connect-local-servers>.
It has not been tested with this server: **Unverified**.

1. In the Claude menu (the menu bar, not the chat window), choose
   **Settings...**, then **Developer**, then **Edit Config**.
2. That opens `claude_desktop_config.json`: on macOS in
   `~/Library/Application Support/Claude/`, on Windows in
   `%APPDATA%\Claude\`.
3. Add the server under `mcpServers`, with full paths, not relative ones:

```json
{
  "mcpServers": {
    "software-lifecycle": {
      "command": "python3",
      "args": ["/path/to/software-lifecycle/swlc_mcp.py"]
    }
  }
}
```

4. Quit Claude Desktop completely and start it again.

If the server does not show up, the page above says the logs are in
`~/Library/Logs/Claude` on macOS and `%APPDATA%\Claude\logs` on Windows.
Whether Claude Desktop finds `python3` on its own: **Unverified**. If it
does not, give the full path to Python as the command (run `which
python3` on macOS, or `where py` on Windows, to find it).

The same page says a local server runs with your user account's
permissions. This server only runs the two commands above, but other
servers you add may do much more.

## A prompt to use

```text
Use only the software-lifecycle tools. My inventory is confidential.
Do not open, read, upload, summarise or quote my inventory or the files
report.md, report.csv or report.json, with any tool.
1. Run preflight on ~/inventories/inventory.csv and tell me if anything
   must be fixed.
2. If nothing must be fixed, run check_counts on the same path.
3. Tell me the counts in plain words. Say "Not found" or "Unverified"
   instead of guessing. Do not paste the results anywhere else.
```

Replace the path with the full path to your inventory.
