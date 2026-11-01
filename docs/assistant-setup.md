# Set up an AI assistant to run the tool

This page helps you get an AI assistant to run `software-lifecycle` for you.
Product facts were checked on 2026-11-01. These products change often, so
check the product's own docs before you rely on a detail.

If you would rather run it yourself, use [quick-start.md](quick-start.md).

## Which assistant can run this?

Only an assistant that runs commands on your own computer can run the tool.
A chat assistant that cannot do that can still guide you: you run the
commands and tell it only the counts.

| Assistant | Can run it on your computer | Needs | Privacy note |
|---|---|---|---|
| Claude Code | Yes, in a local session. It asks before it runs a command in Manual mode. | The repo in a folder on your computer. A Claude account (Pro, Max, Team, Enterprise or Console). Start it with `claude` inside the folder. | Everything it reads is sent to Anthropic. Its sandbox is off by default. Its instruction files are context, not enforced rules. |
| Codex (CLI or IDE extension) | Yes, in a local session in your project folder. | The repo in a folder on your computer. Install it from OpenAI's Codex docs and sign in with ChatGPT. Start it with `codex` inside the folder. | OpenAI's docs warn that prompts can include sensitive data. Locally it has no network access by default, and it writes only inside the workspace. |
| ChatGPT desktop app | Yes, through its local Codex mode, with a local project folder. Which plans include it: not confirmed. Check OpenAI's docs. | The repo in a folder on your computer. | Uploaded files go to OpenAI. On macOS, the older "Work with Apps" feature sends the last 200 lines of open terminal panes in each message. Do not use it here. |
| GitHub Copilot (CLI and VS Code agent mode) | Yes, in the terminal CLI or in VS Code agent mode. Both ask you before they run a command. | The repo in a folder on your computer. The CLI asks you to trust the folder, then you run `/login`. Install steps: see GitHub's Copilot CLI docs. | Not checked against a source. The rule below applies: anything it opens goes to its provider. |
| Claude Desktop chat | No. Guide only: you run the commands. | Nothing. | Plain chat cannot run commands on your computer. Its "Code execution and file creation" runs in a sandbox hosted by Anthropic, so a file you upload leaves your computer. To run commands, use Claude Code (see the first row). |
| Perplexity | No. Guide only: you run the commands. | Nothing. | No way to run a local command was confirmed. Files you upload to a Project are stored there. |
| Any other chat assistant | No. Guide only: you run the commands. | Nothing. | Not checked against a source. Treat it like the chat rows above. |
| Copilot coding agent, Codex cloud, hosted sandboxes | Do not use with a real inventory. | Not applicable. | These work on a repo copy or an uploaded file held by the provider. A real inventory would leave your computer. |

## The privacy rule

Anything an assistant opens goes to the company that runs it. If it opens
your inventory, your inventory goes to that company.

- The prompts below tell the assistant not to open your inventory or the
  report files. That is a request. Nothing technical stops an assistant
  from ignoring it. Some products have a permission setting that can block
  a file. See the product's own docs.
- `--counts-only` prints counts and item IDs, with no names, versions,
  publishers or owners. The full report is still written to the `--out`
  folder.
- `preflight` prints your column titles and counts, never a cell. The
  assistant will see the column titles.
- Keep the inventory and the report folder outside the tool's folder, and
  start the assistant in the tool's folder only.
- Never attach or paste the inventory or a report into a chat.
- Item IDs are hashes with no secret in them. Treat them with the same care
  as the inventory. See "Counts-only mode" in [usage.md](usage.md).

## Before you start

1. Download or clone the repo into a new folder, for example
   `Documents/software-lifecycle`. Do this yourself first: not every
   assistant can clone.
2. Put your export next to that folder as `inventory.csv`, outside the
   tool's folder. The report will go to `swlc-out`, also outside it. The
   layout is the same as in [quick-start.md](quick-start.md).
3. Open the assistant inside the `software-lifecycle` folder.
4. Keep command approval on. Read each command before you allow it. You
   should see only the commands in the prompt.

How to start each one (checked 2026-11-01):

- Claude Code: go into the folder, run `claude`, log in. Docs:
  <https://code.claude.com/docs/en/quickstart>
- Codex CLI: go into the folder, run `codex`, sign in with ChatGPT. Docs:
  <https://learn.chatgpt.com/docs/codex/cli>
- ChatGPT desktop app: pick the local project folder. Choose "Ask for
  approval" under the composer so the sandbox stays on. Docs:
  <https://learn.chatgpt.com/docs/app>
- GitHub Copilot CLI: go into the folder, run `copilot`, then `/login`. For
  VS Code agent mode, see the VS Code and GitHub Copilot docs.

## Prompts

Copy the prompt that fits your assistant. Change `../inventory.csv` and
`../swlc-out` if your paths differ. On Windows the prompt already says to
use `py`.

### Claude Code, Codex, GitHub Copilot

```text
Help me run software-lifecycle on my software inventory. The inventory is confidential.

Rules:
- Do not open, read, print, summarise or quote my inventory file. Do not open, print or summarise report.md, report.csv or report.json. Do not upload or attach any of them.
- Do not run anything that uses the network. Do not run refresh_data.py unless I ask for it by name.
- If you do not know something, say "Not found" or "Unverified". Do not guess.

Steps:
1. Check Python is 3.9 or newer: run `python3 --version` (on Windows, `py --version`). If it is older or missing, stop and tell me. On Windows use `py` in place of `python3` below.
2. The tool should be in the current folder (software_lifecycle.py). If it is not, ask me before you clone https://github.com/evemcgivern/software-lifecycle into a NEW folder. Do not install anything.
3. Run `python3 software_lifecycle.py preflight ../inventory.csv`. It prints column titles and counts, never a cell. Tell me what it says. If it lists problems, tell me what to fix in the export. Do not open the file to fix it.
4. Run `python3 software_lifecycle.py check ../inventory.csv --counts-only --out ../swlc-out`.
5. Give me only the counts it printed. Do not list the item IDs back to me. Tell me the full report is in ../swlc-out (report.md, report.csv, report.json) and that I will read it myself.
```

### ChatGPT desktop app

```text
Help me run software-lifecycle on my software inventory. The inventory is confidential. Work only in my local project folder. Do not use a cloud environment, and do not use any other app's content.

Rules:
- Do not open, read, print, summarise or quote my inventory file. Do not open, print or summarise report.md, report.csv or report.json. Do not upload or attach any of them.
- Do not run anything that uses the network. Do not run refresh_data.py unless I ask for it by name.
- If you do not know something, say "Not found" or "Unverified". Do not guess.

Steps:
1. Check Python is 3.9 or newer: run `python3 --version` (on Windows, `py --version`). If it is older or missing, stop and tell me. On Windows use `py` in place of `python3` below.
2. The tool should be in the current folder (software_lifecycle.py). If it is not, tell me and stop. Do not clone or install anything.
3. Run `python3 software_lifecycle.py preflight ../inventory.csv`. It prints column titles and counts, never a cell. Tell me what it says. If it lists problems, tell me what to fix in the export. Do not open the file to fix it.
4. Run `python3 software_lifecycle.py check ../inventory.csv --counts-only --out ../swlc-out`.
5. Give me only the counts it printed. Do not list the item IDs back to me. Tell me the full report is in ../swlc-out (report.md, report.csv, report.json) and that I will read it myself.
```

### Claude Desktop chat, Perplexity, any other chat assistant

```text
I will run software-lifecycle myself in my own terminal. You cannot run commands, so guide me. My inventory is confidential.

Rules:
- Never ask me to paste, attach or upload my inventory file or the files report.md, report.csv and report.json. If I paste one by mistake, tell me to stop and do not use it.
- Do not tell me to run anything that uses the network. Do not tell me to run refresh_data.py.
- If you do not know something, say "Not found" or "Unverified". Do not guess.

Guide me one step at a time. Wait for me to answer before the next step:
1. Tell me how to open a terminal on my system, and how to check that Python is 3.9 or newer: `python3 --version` (on Windows, `py --version`).
2. Tell me to put the software-lifecycle repo in a NEW folder and to open the terminal in that folder.
3. Tell me to run `python3 software_lifecycle.py preflight ../inventory.csv`, and to paste back only what it prints. It shows column titles and counts, never a cell. Help me fix any problem it names in my export.
4. Tell me to run `python3 software_lifecycle.py check ../inventory.csv --counts-only --out ../swlc-out`, and to paste back only the counts.
5. Explain the counts in plain words. Tell me the full report is in ../swlc-out and that I should read it myself.
```

## What to do with the counts

The counts tell you how many items are on each list. The names are in the
report files, which you read yourself. See "Counts-only mode" in
[usage.md](usage.md) for each line, [glossary.md](glossary.md) for the
words, and [sop.md](sop.md) for the review steps.

## If your assistant cannot run commands

Run the same commands yourself in a terminal, from the tool's folder:

    python3 software_lifecycle.py preflight ../inventory.csv
    python3 software_lifecycle.py check ../inventory.csv --counts-only --out ../swlc-out

On Windows, type `py` in place of `python3`. Paste back only the lines the
commands print. Never paste the inventory or the report files.

## Files in the repo for other tools

The repo root has [AGENTS.md](../AGENTS.md) and [CLAUDE.md](../CLAUDE.md).
They point assistants that read project instruction files at these steps.
Claude Code reads `CLAUDE.md` first, and reads `AGENTS.md` only when there
is no `CLAUDE.md`, so `CLAUDE.md` here imports `AGENTS.md`. Codex and
GitHub Copilot read `AGENTS.md`. These files are instructions, not
enforced rules.
