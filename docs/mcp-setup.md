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

## Tested so far

The maintainer tested the server by hand on 2026-11-01, on one Mac
(macOS 27.2), with the synthetic demo inventory from `examples/` copied
to a folder outside the repo. App versions were not recorded. Nothing
else was tested, except the package described below: every other detail
on this page stays **Unverified**.

**Claude Desktop.**

- Set up through `claude_desktop_config.json` (**Settings**,
  **Developer**, **Edit Config**), with the full path to Python
  (`/opt/homebrew/bin/python3`, a Homebrew install) as the command and the
  full path to `swlc_mcp.py` as the argument. No working directory was
  set.
- The server showed as a connector named `software-lifecycle` with both
  tools.
- The app lists `preflight` under **Read-only tools** and `check_counts`
  under **Write/delete tools**. The server marks `check_counts` as not
  read-only (it writes the report folder); the app's label may come from
  that: not confirmed. Both are listed as **Needs approval** in the
  connector's settings screen.
- The approval prompt was seen in a second run the same day (chat model
  Sonnet 5.5, approval mode **Manual**, the prompt from
  [A prompt to use](#a-prompt-to-use)). Before each tool ran, Claude
  Desktop asked first: "Claude wants to use Preflight from
  software-lifecycle", and later "Claude wants to use Check counts from
  software-lifecycle". Each prompt showed the full path to the demo file
  and three buttons: **Decline**, **Always allow** and **Allow once**.
  **Allow once** was chosen both times. Both tools then ran, and the chat
  gave the counts below and said it had not opened the report or the
  inventory.
- Both tools ran and returned only counts: no names, versions, publishers,
  column titles or item IDs.
- Not tested: a bare `python3` as the command. Whether Claude Desktop finds
  `python3` by itself is **Unverified**; the tested setup used the full
  path.

**ChatGPT desktop app.**

- The app saved the server in `~/.codex/config.toml` as
  `[mcp_servers.software-lifecycle]` with `enabled`, `command` (the full
  path to Python) and `args`. The entry the app saved has no working directory, and the tool ran;
  leave it blank.
- Both tools ran and returned only the same counts.
- That test ran with ChatGPT set to **Full Access**, so the approval
  prompt was not tested: **Unverified**.
- The three safety settings (`enabled_tools`,
  `default_tools_approval_mode = "prompt"` and `tool_timeout_sec = 300`)
  were added to `config.toml` after the test and have not been tested.
  They are the keys OpenAI documents. This page does not claim they work.

**What both apps returned on the demo inventory** (bundled data, `checked_on`
2026-11-01): 60 rows, 50 items, a count total of 11,791, all 50 items unmatched,
and a classification of 48 `unknown`, 1 `bundle_member` and 1
`component`. All 50 are unmatched because the demo uses made-up product
names that only match the test data. The repo's own demo command uses
`--data tests/fixtures/data --as-of 2026-10-24` for that reason. This is
expected, not a fault.

**Treat the chat's guesses about causes as unverified.** A chat app sees
only counts, so its explanation of why a result looks as it does can be
wrong. In one test the chat guessed that the empty end-of-life column
caused the unmatched items; that was wrong. In the package run (below)
the chat added a "blank publisher" and said the check "ran against the
generic profile"; the tool reported neither. The report folder holds the
facts.

**One-click package (Claude Desktop).** The maintainer tested the
`.mcpb` package (issue #66) on 2026-11-01, on the same Mac (macOS 27.2),
after removing the manual entry from the config file. It was installed
and run once. Everything below is what was seen on that one Mac; the
rest is **Unverified**.

- Built with `python3 tools/build_mcpb.py --out <folder>`: 514 files,
  366,553 bytes, named `software-lifecycle-0.6.0.mcpb` (the version file
  said 0.6.0), SHA-256
  `9decb540eb7a492ea689e7b24dab5e2382ae553b0ce562a67d40c739d28e8c01`.
- Opening the file in Claude Desktop showed an install dialog: the name
  "software-lifecycle (counts only)", the manifest's author, the MIT
  license, "All requirements met", and both tools listed. The dialog also
  showed Claude Desktop's own warning: "Installing will grant this
  extension access to everything on your computer. Any developer
  information shown has not been verified by Anthropic. Ensure you trust
  the source of this extension before installation." No other signing
  prompt was seen. After **Install**, the app showed an **Uninstall**
  button, an **Enabled** toggle (on) and a **Configure** button.
- The extension was installed in `~/Library/Application Support/Claude/Claude
  Extensions/local.mcpb.<author-slug>.software-lifecycle`. It holds a
  `.venv` folder and a `uv.lock` file, which the app's uv created at
  install (manifest version 0.4, server type `uv`; the venv's
  `pyvenv.cfg` names uv 0.12.1 and CPython 3.13 from uv's own Python
  folder).
- **That Mac already had uv 0.12.1 (`~/.local/bin/uv`) and a cached
  CPython 3.13.14 in uv's Python folder from earlier use.** So a fast
  install with no download does not show that a Mac without uv, or
  without that Python, works. **Unverified**: a Mac without uv or without
  a cached Python; whether the app downloads a Python on first run and
  needs the network to do so; Windows; whether Claude Desktop uses its
  own uv or the one on the `PATH`.
- With the demo inventory (copied outside the repo) and the prompt in
  [A prompt to use](#a-prompt-to-use), each tool showed an approval prompt
  with the path. **Allow once** was chosen for both. Both tools ran, and
  the counts matched the manual-config runs exactly: 60 rows, 50 items, a
  count total of 11,791, all 50 unmatched, and a classification of 48
  `unknown`, 1 `bundle_member` and 1 `component`. No names, versions,
  publishers, column titles or item IDs came back. The app's log for the
  extension shows `initialize` and `tools/list`, and the server's start
  line.
- The chat's own commentary on that run held two statements the tool did
  not support: it added a "blank publisher", and said the check "ran
  against the generic profile". See the paragraph above on the chat's
  guesses.

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

5. Find the full path to Python: run `which python3` (on Windows,
   `where py`). Use that full path as the command in both apps, for
   example `/opt/homebrew/bin/python3` for a Homebrew install. Apps you
   start from the Dock or Start menu may not search the same folders as
   your terminal, so they may not find a bare `python3` (reason not
   confirmed). The full path avoids that. Leave the
   working directory blank.

In the settings below, replace `/path/to/python3` with that full path and
`/path/to/software-lifecycle` with the full path of your repo folder. On
Windows, use the command `py`, the
arguments `-3` and the path, and write each backslash in a path twice in
JSON (`C:\\tools\\software-lifecycle\\swlc_mcp.py`).

## ChatGPT desktop app

Source: <https://learn.chatgpt.com/docs/extend/mcp?surface=desktop>
(no last-updated date shown). Both tools ran once on one Mac on
2026-11-01 with ChatGPT set to **Full Access**; see
[Tested so far](#tested-so-far). The approval prompt was not tested:
**Unverified**.

In the app:

1. Open **Settings**, then select **MCP servers**.
2. Select **Add server**.
3. Enter a name (for example `software-lifecycle`), choose **STDIO**, and
   give the full path to Python as the command and the argument
   `/path/to/software-lifecycle/swlc_mcp.py`. Leave the working directory
   blank.
4. Save the server, then select **Restart**.

The app saved the server in `~/.codex/config.toml`, which the desktop app,
the Codex CLI and the IDE extension share. You can also edit that file
yourself. The first four lines below are what the app wrote in the test.
The last three are the safety settings. They were added after the test and
have not been tested; they are the key names from OpenAI's page:

```toml
[mcp_servers.software-lifecycle]
enabled = true
command = "/path/to/python3"
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

The one-click package for Claude Desktop (a `.mcpb` file) was installed
and run once on one Mac on 2026-11-01; everything else about it is
**Unverified**. See
[One-click package (Claude Desktop)](#one-click-package-claude-desktop).
The manual route below is the longest-tested one.

The manual route below is documented for local servers in general:
<https://modelcontextprotocol.io/docs/develop/connect-local-servers>.
It worked once with this server on one Mac on 2026-11-01; see
[Tested so far](#tested-so-far). Other computers and app versions:
**Unverified**.

1. In the Claude menu (the menu bar, not the chat window), choose
   **Settings...**, then **Developer**, then **Edit Config**.
2. That opens `claude_desktop_config.json`: on macOS in
   `~/Library/Application Support/Claude/`, on Windows in
   `%APPDATA%\Claude\`.
3. Add the server under `mcpServers`, with full paths, not relative ones.
   Use the full path to Python as the command, and set no working
   directory:

```json
{
  "mcpServers": {
    "software-lifecycle": {
      "command": "/path/to/python3",
      "args": ["/path/to/software-lifecycle/swlc_mcp.py"]
    }
  }
}
```

4. Quit Claude Desktop completely and start it again.

If the server does not show up, the page above says the logs are in
`~/Library/Logs/Claude` on macOS and `%APPDATA%\Claude\logs` on Windows.
Whether Claude Desktop finds a bare `python3` on its own: **Unverified**;
the tested setup used the full path to Python (run `which python3` on
macOS, or `where py` on Windows, to find it).

In the connector's settings Claude Desktop sorts the tools by what they
do. `preflight` is listed under **Read-only tools**. `check_counts` is
listed under **Write/delete tools**; the server marks it as not
read-only because it writes the report folder next to your CSV, and the
app's label may come from that (not confirmed). Both are listed as
**Needs approval**. Keep that, so you see the path before each run.

Before each tool runs, Claude Desktop asks first and shows the path, with
the buttons **Decline**, **Always allow** and **Allow once** (seen once on
one Mac, 2026-11-01). Choose **Allow once**, so you see the path each
time. **Always allow** removes that check.

The same page says a local server runs with your user account's
permissions. This server only runs the two commands above, but other
servers you add may do much more.

## One-click package (Claude Desktop)

The repo can build a Desktop Extension: one `.mcpb` file that holds
`swlc_mcp.py`, the tool, its bundled data, `LICENSE` and
`THIRD-PARTY.md`, and nothing else (no tests, examples, docs or CSV
files). It was installed and run once on one Mac on 2026-11-01 (see
[Tested so far](#tested-so-far)); anything beyond that is **Unverified**.
The manual route in [Claude Desktop](#claude-desktop) remains the
longest-tested one.

Build it from the repo folder:

```text
python3 tools/build_mcpb.py --out ../swlc-package
```

It writes `software-lifecycle-<version>.mcpb` to that folder (without
`--out`, to `dist/`, which git ignores) and prints every file in the
package and the SHA-256 of the package. The same files give the same
bytes on every build. It stops if any file not on its allow-list would go
in.

To install it, open the `.mcpb` file with Claude Desktop (for example by
double-clicking it). The MCPB project's README says that shows an
installation dialog:
<https://github.com/modelcontextprotocol/mcpb> (no last-updated date
shown). An install button under **Settings**, **Extensions**: not
confirmed in a doc this page cites, **Unverified**.

What to know first:

- The package is unsigned. On the tested Mac the install dialog showed
  Claude Desktop's warning that the extension gets access to everything
  on your computer (quoted in [Tested so far](#tested-so-far)). Read it
  before you click **Install**.
- It uses the `uv` server type from the MCPB manifest spec (manifest
  version 0.4). The spec says the host app manages Python for such a
  package. The package declares no third-party packages. The Python that
  Claude Desktop's uv picks must be 3.9 or newer. The tested Mac already had uv and a cached
  Python, so a download was not seen. Whether uv downloads
  one the first time, and whether it needs the network to do so:
  **Unverified**. Whether your version of Claude Desktop supports the
  `uv` type, and runs this server with it: **Unverified**.
- On the tested Mac the app's uv wrote a `.venv` folder and a `uv.lock`
  file inside the extension folder at install. Other computers:
  **Unverified**.
- "No network by default" is about this project's own code. It says nothing
  about what Claude Desktop or its uv does to start Python.
- It offers the same two tools, with the same limits and the same
  protections as the manual route. Everything in
  [What it protects, and what it does not](#what-it-protects-and-what-it-does-not)
  still applies. On the tested Mac, Claude Desktop asked before each
  tool ran, as it did with the manual route; other computers and app
  versions: **Unverified**.
- Remove a manual entry of the same name (`software-lifecycle`) from
  `claude_desktop_config.json` before you install the package, so the
  tools do not show up twice.

If it fails to install or the tools do not show up, look in the logs in
`~/Library/Logs/Claude` on macOS (`%APPDATA%\Claude\logs` on Windows),
remove the extension, and use the manual route instead.

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
