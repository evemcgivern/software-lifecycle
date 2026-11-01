#!/usr/bin/env python3
"""A counts-only MCP server for software-lifecycle (stdio transport).

Run it as `python3 swlc_mcp.py` (on Windows, `py -3 swlc_mcp.py`). A chat
app starts it and talks JSON-RPC over stdin and stdout, one message per
line (MCP 2025-11-25). It offers exactly two tools:

- check_counts: runs `check PATH --counts-only --out DIR` and returns only
  the summary counts, rebuilt from fixed labels and parsed numbers.
- preflight: runs `preflight PATH --json` and returns only fixed labels,
  numbers and true/false values.

Nothing read from the inventory reaches the model: no names, cells,
column titles or item IDs. Standard library only, no network. It never
runs refresh_data.py. Logs go to stderr; stdout carries only messages.
"""
from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = ROOT / "software_lifecycle.py"

PROTOCOL_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
MAX_MESSAGE_BYTES = 1024 * 1024
MAX_PATH_CHARS = 4096
# The same cap the tool itself puts on an inventory (swlc/inputs.py).
MAX_CSV_BYTES = 256 * 1024 * 1024
MAX_CHILD_STDOUT = 64 * 1024 * 1024
TIMEOUT_SECONDS = 280
MAX_OUTPUT_CHARS = 4000
OUT_NAME = "swlc-out"

PARSE_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND = -32700, -32600, -32601
INVALID_PARAMS, INTERNAL_ERROR = -32602, -32603

# Fixed key sets, kept equal to swlc/assess.py and swlc/classify.py by
# tests/test_mcp.py.
STATES = ("supported", "mainstream_ended", "ends_soon", "past_eol",
          "unmatched")
CLASSES = ("governable", "component", "bundle_member", "unknown")
LISTS = ("past_eol", "ends_soon", "dates_disagree", "unmatched",
         "accepted_risk", "ownerless", "review_urgently", "golden_overrides")
FIELDS = ("name", "publisher", "version", "owner", "count", "export_eol",
          "parent")
LINE_ENDINGS = ("CRLF", "LF", "CR", "mixed", "none", "unknown")

PRIVACY = ("Counts only. Never open, read, upload, summarise or quote the "
           "inventory file or the report files (report.md, report.csv, "
           "report.json), with this or any other tool. Tell the user the "
           "counts in plain words and do not paste them anywhere else.")

TOOLS = [
    {
        "name": "check_counts",
        "title": "Check an inventory (counts only)",
        "description": (
            "Runs the software-lifecycle check on one inventory CSV on "
            "this computer, offline, and returns summary counts only: no "
            "names, versions, publishers, owners or item IDs. Pass the "
            "full path to a .csv file. The full report is written to a "
            "folder named swlc-out next to the file; the result gives its "
            "path so the user can open it themselves. " + PRIVACY),
        "inputSchema": {
            "type": "object",
            "properties": {"path": {
                "type": "string",
                "description": "Full path to the inventory .csv file."}},
            "required": ["path"],
            "additionalProperties": False,
        },
        # It writes the three report files, so it is not read-only.
        "annotations": {"title": "Check an inventory (counts only)",
                        "readOnlyHint": False, "destructiveHint": False,
                        "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "preflight",
        "title": "Preflight an inventory (numbers only)",
        "description": (
            "Says whether the check can use one inventory CSV on this "
            "computer. Reads the file locally and returns only numbers, "
            "true/false values and fixed codes: no cell text and no "
            "column titles. Writes nothing. Pass the full path to a .csv "
            "file. " + PRIVACY),
        "inputSchema": {
            "type": "object",
            "properties": {"path": {
                "type": "string",
                "description": "Full path to the inventory .csv file."}},
            "required": ["path"],
            "additionalProperties": False,
        },
        "annotations": {"title": "Preflight an inventory (numbers only)",
                        "readOnlyHint": True, "openWorldHint": False},
    },
]
TOOL_NAMES = tuple(t["name"] for t in TOOLS)


def log(text: str) -> None:
    """Fixed-format log lines to stderr; never file content."""
    try:
        sys.stderr.write("swlc_mcp: %s\n" % text)
        sys.stderr.flush()
    except (OSError, ValueError):
        pass


# --- path rules -------------------------------------------------------------

class PathError(Exception):
    """A refused path. Its text is fixed and never holds file content."""


def check_path(text) -> Path:
    """Return the resolved inventory path, or raise PathError.

    Rules: a non-empty string with no control characters (NUL included),
    at most MAX_PATH_CHARS long, absolute after ~ expansion, not a
    symlink (as given or resolved), ending in .csv (any case), a regular
    file (not a directory, device or FIFO), at most MAX_CSV_BYTES. The
    path is resolved first and the checks run on the result."""
    if not isinstance(text, str) or not text:
        raise PathError("path must be a non-empty string")
    if len(text) > MAX_PATH_CHARS:
        raise PathError("path is longer than %d characters" % MAX_PATH_CHARS)
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in text):
        raise PathError("path contains a control character")
    given = Path(os.path.expanduser(text))
    if not given.is_absolute():
        raise PathError("give the full path to the file, not a relative one")
    try:
        if given.is_symlink():
            raise PathError("refusing a symlink; give the real file's path")
        resolved = given.resolve(strict=True)
    except PathError:
        raise
    except FileNotFoundError:
        raise PathError("no file at that path") from None
    except (OSError, RuntimeError, ValueError):
        raise PathError("that path cannot be read") from None
    for name in (given.name, resolved.name):
        if not name.lower().endswith(".csv") or name.lower() == ".csv":
            raise PathError("the file must end in .csv")
    try:
        info = os.lstat(str(resolved))
    except (OSError, ValueError):
        raise PathError("that path cannot be read") from None
    if stat.S_ISLNK(info.st_mode):
        raise PathError("refusing a symlink; give the real file's path")
    if not stat.S_ISREG(info.st_mode):
        raise PathError("not a regular file")
    if info.st_size > MAX_CSV_BYTES:
        raise PathError("the file is larger than %d bytes" % MAX_CSV_BYTES)
    return resolved


def out_dir_for(csv_path: Path) -> Path:
    out = csv_path.parent / OUT_NAME
    if os.path.lexists(str(out)) and (out.is_symlink() or not out.is_dir()):
        raise PathError("%s next to the file is not a plain folder; move or "
                        "rename it" % OUT_NAME)
    return out


# --- running the tool --------------------------------------------------------

def _env() -> dict:
    env = {"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    for key in ("SYSTEMROOT", "SystemRoot"):  # Windows needs it to start
        if key in os.environ:
            env[key] = os.environ[key]
    return env


def run_cli(args: list) -> tuple:
    """Run the CLI with a fixed argument list. Return (exit code, stdout
    text). stderr is discarded: it is never forwarded."""
    argv = [sys.executable, "-I", "-B", str(CLI)] + [str(a) for a in args]
    proc = subprocess.run(argv, cwd=str(ROOT), env=_env(), shell=False,
                          stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL,
                          timeout=TIMEOUT_SECONDS)
    out = proc.stdout[:MAX_CHILD_STDOUT]
    return proc.returncode, out.decode("utf-8", "replace")


EXIT_TEXT = {
    2: "the tool refused the arguments",
    3: "the tool could not use this file; run the preflight tool on it, or "
       "run the tool yourself in a terminal for details",
    4: "the tool's bundled data failed its check; run python3 "
       "software_lifecycle.py verify-data in a terminal",
}


def exit_message(code: int) -> str:
    return "%s (exit code %d)" % (
        EXIT_TEXT.get(code, "the tool stopped with an error"), code)


# --- counts-only output: an allow-list, rebuilt from parsed values ---------

_DATE = re.compile(r"checked_on ([0-9]{4}-[0-9]{2}-[0-9]{2})")
_KEV = re.compile(r"kev_current (true|false)")
_ITEMS = re.compile(r"items ([0-9]{1,12}) rows ([0-9]{1,12})")
_PAIRS = re.compile(r"(states|classification)((?: [a-z_]{1,40}=[0-9]{1,12})+)")
_AMBIG = re.compile(r"ambiguous_review ([0-9]{1,12})")
_SUPPORT = re.compile(r"support_records listed=([0-9]{1,12}) "
                      r"ending_soon=([0-9]{1,12}) not_matched=([0-9]{1,12})")
_TOTAL = re.compile(r"count_total ([0-9]{1,15})")
_LIST = re.compile(r"(%s) ([0-9]{1,12})(?:: [0-9a-f]{12}(?: [0-9a-f]{12})*)?"
                   % "|".join(LISTS))


def counts_lines(stdout: str) -> list:
    """Keep only the summary lines the allow-list knows, each rebuilt from
    a fixed label and parsed numbers. Every other line is dropped. A list
    line keeps its name and count; its item IDs are never copied."""
    keys = {"states": STATES, "classification": CLASSES}
    out = []
    for line in stdout.split("\n"):
        line = line.rstrip("\r")
        m = _DATE.fullmatch(line)
        if m:
            out.append("checked_on %s" % m.group(1))
            continue
        m = _KEV.fullmatch(line)
        if m:
            out.append("kev_current %s" % m.group(1))
            continue
        m = _ITEMS.fullmatch(line)
        if m:
            out.append("items %d rows %d" % (int(m.group(1)),
                                             int(m.group(2))))
            continue
        m = _PAIRS.fullmatch(line)
        if m:
            pairs = [p.split("=") for p in m.group(2).split()]
            if all(k in keys[m.group(1)] for k, _ in pairs):
                out.append(m.group(1) + " " + " ".join(
                    "%s=%d" % (k, int(v)) for k, v in pairs))
            continue
        m = _AMBIG.fullmatch(line)
        if m:
            out.append("ambiguous_review %d" % int(m.group(1)))
            continue
        m = _SUPPORT.fullmatch(line)
        if m:
            out.append("support_records listed=%d ending_soon=%d "
                       "not_matched=%d" % tuple(int(g) for g in m.groups()))
            continue
        m = _TOTAL.fullmatch(line)
        if m:
            out.append("count_total %d" % int(m.group(1)))
            continue
        m = _LIST.fullmatch(line)
        if m:
            out.append("%s %d" % (m.group(1), int(m.group(2))))
    return out


def cap(text: str) -> str:
    """Hard length cap: cut at the last whole line that fits."""
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    marker = "\n[output cut at %d characters]" % MAX_OUTPUT_CHARS
    keep = text[:max(0, MAX_OUTPUT_CHARS - len(marker))]
    keep = keep[:keep.rfind("\n")] if "\n" in keep else ""
    return keep + marker


def tool_check_counts(path: Path) -> tuple:
    out = out_dir_for(path)
    code, stdout = run_cli(["check", str(path), "--counts-only",
                            "--out", str(out)])
    if code != 0:
        return True, exit_message(code)
    lines = counts_lines(stdout)
    if not lines or not lines[0].startswith("checked_on "):
        return True, "the tool's output was not in the expected form"
    lines += [
        "note: counts are from your file; count_total is the sum of its "
        "count column",
        "note: the full report is in the folder %s; the user can open it. "
        "Do not open, read or quote it." % out,
    ]
    return False, cap("\n".join(lines))


def _int(value) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("not a count")
    return value


def _bool(value) -> bool:
    if not isinstance(value, bool):
        raise ValueError("not a boolean")
    return value


_PROFILE = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
_CODE = re.compile(r"[A-Z][A-Z_]{0,39}")


def preflight_lines(result: dict) -> list:
    """Fixed labels with numbers, true/false and fixed codes only. Column
    titles, the next command, the profile explanation and fix texts are
    all dropped."""
    f, lim, prof = result["file"], result["limits"], result["profile"]
    ending = f["line_endings"]
    if ending not in LINE_ENDINGS:
        ending = "unknown"
    names = []
    for key in ("best", "used"):
        name = prof[key]
        names.append(name if isinstance(name, str)
                     and _PROFILE.fullmatch(name) else "other")
    cols, blank = result["columns"], result["blank_cells"]
    found = ["%s=%s" % (k, "true" if cols.get(k) else "false")
             for k in FIELDS]
    blanks = ["%s=%d" % (k, _int(blank[k])) for k in FIELDS if k in blank]
    codes, must = [], []
    for item in result["fix"]:
        code = item["code"]
        if isinstance(code, str) and _CODE.fullmatch(code):
            (must if _bool(item["blocking"]) else codes).append(code)
    placeholder = result["placeholder_cells"].get("parent")
    return [
        "preflight_ok %s" % ("true" if _bool(result["ok"]) else "false"),
        "data_rows %d" % _int(f["rows"]),
        "bytes %d" % _int(f["bytes"]),
        "byte_order_mark %s" % ("true" if _bool(f["bom"]) else "false"),
        "line_endings %s" % ending,
        "within_limits %s" % ("true" if _bool(lim["within"]) else "false"),
        "profile_best_fit %s" % names[0],
        "profile_used %s" % names[1],
        "columns_found " + " ".join(found),
        "blank_cells " + (" ".join(blanks) or "none"),
        "placeholder_parent_cells %s" % (
            "%d" % _int(placeholder) if placeholder is not None else "none"),
        "formula_like_cells %d" % _int(result["formula_cells"]),
        "unreadable_date_cells %d" % _int(result["unreadable_date_cells"]),
        "must_fix " + (" ".join(must) or "none"),
        "other_fix " + (" ".join(codes) or "none"),
    ]


def tool_preflight(path: Path) -> tuple:
    code, stdout = run_cli(["preflight", str(path), "--json"])
    if code not in (0, 3):
        return True, exit_message(code)
    try:
        result = json.loads(stdout)
        if not isinstance(result, dict) or "file" not in result:
            return True, exit_message(code)
        lines = preflight_lines(result)
    except (ValueError, KeyError, TypeError, AttributeError):
        return True, "the tool's output was not in the expected form"
    lines.append("note: run preflight in a terminal to see the full "
                 "advice; the fix codes are explained in docs/mcp-setup.md")
    return False, cap("\n".join(lines))


RUNNERS = {"check_counts": tool_check_counts, "preflight": tool_preflight}


def call_tool(name: str, arguments) -> dict:
    """Run one tool. Every failure is a tool result with isError true and a
    fixed message."""
    if not isinstance(arguments, dict) or set(arguments) != {"path"}:
        is_error, text = True, ("this tool takes exactly one argument, "
                                "path")
    else:
        try:
            is_error, text = RUNNERS[name](check_path(arguments["path"]))
        except PathError as exc:
            is_error, text = True, "refused: %s" % exc
        except subprocess.TimeoutExpired:
            is_error, text = True, ("the tool took longer than %d seconds "
                                    "and was stopped" % TIMEOUT_SECONDS)
        except OSError:
            is_error, text = True, "the tool could not be started"
    return {"content": [{"type": "text", "text": text}],
            "isError": is_error}


# --- JSON-RPC over stdio ----------------------------------------------------

class RpcError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def server_version() -> str:
    try:
        text = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "0"
    return text if re.fullmatch(r"[0-9A-Za-z.+-]{1,40}", text) else "0"


def handle_initialize(params: dict) -> dict:
    asked = params.get("protocolVersion")
    version = asked if asked in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0]
    return {
        "protocolVersion": version,
        "capabilities": {"tools": {"listChanged": False}},
        "serverInfo": {"name": "software-lifecycle",
                       "title": "software-lifecycle (counts only)",
                       "version": server_version()},
        "instructions": (
            "Two tools: preflight and check_counts. Each takes the full "
            "path to an inventory .csv file and returns counts only. "
            + PRIVACY),
    }


def handle_call(params: dict) -> dict:
    name = params.get("name")
    if name not in TOOL_NAMES:
        raise RpcError(INVALID_PARAMS, "Unknown tool")
    return call_tool(name, params.get("arguments", {}))


def dispatch(msg) -> dict | None:
    """Return the reply for one parsed message, or None for no reply."""
    if not isinstance(msg, dict):
        return error_reply(None, INVALID_REQUEST, "Invalid Request")
    has_id = "id" in msg
    rid = msg.get("id")
    if "method" not in msg:
        return None  # a response from the client: nothing to answer
    id_ok = isinstance(rid, (str, int)) and not isinstance(rid, bool)
    method = msg.get("method")
    if msg.get("jsonrpc") != "2.0" or not isinstance(method, str) \
            or (has_id and not id_ok):
        return error_reply(rid if id_ok else None, INVALID_REQUEST,
                           "Invalid Request")
    params = msg.get("params", {})
    if not isinstance(params, dict):
        return error_reply(rid, INVALID_PARAMS, "Invalid params") \
            if has_id else None
    if not has_id:
        return None  # notifications (initialized, cancelled, ...) get none
    try:
        if method == "initialize":
            result = handle_initialize(params)
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            result = handle_call(params)
        else:
            raise RpcError(METHOD_NOT_FOUND, "Method not found")
    except RpcError as exc:
        return error_reply(rid, exc.code, exc.message)
    except Exception as exc:  # never a traceback, never on stdout
        log("internal error: %s" % type(exc).__name__)
        return error_reply(rid, INTERNAL_ERROR, "Internal error")
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def error_reply(rid, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": rid,
            "error": {"code": code, "message": message}}


def handle_line(raw: bytes) -> dict | None:
    if not raw.strip():
        return None
    try:
        msg = json.loads(raw.decode("utf-8"))
    except (ValueError, RecursionError):
        return error_reply(None, PARSE_ERROR, "Parse error")
    return dispatch(msg)


def serve(stdin, stdout) -> None:
    """Read one message per line from stdin (bytes); write one per line to
    stdout (bytes). ASCII-only JSON, so no newline or encoding surprises."""
    while True:
        raw = stdin.readline(MAX_MESSAGE_BYTES + 1)
        if not raw:
            return
        if len(raw) > MAX_MESSAGE_BYTES and not raw.endswith(b"\n"):
            while True:  # drop the rest of the over-long line
                more = stdin.readline(MAX_MESSAGE_BYTES)
                if not more or more.endswith(b"\n"):
                    break
            reply = error_reply(None, INVALID_REQUEST, "Message too large")
        else:
            reply = handle_line(raw)
        if reply is not None:
            stdout.write(json.dumps(reply, ensure_ascii=True,
                                    separators=(",", ":")).encode("ascii")
                         + b"\n")
            stdout.flush()


def main() -> int:
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    except (AttributeError, ValueError):
        pass
    stdin, stdout = sys.stdin.buffer, sys.stdout.buffer
    # Anything printed by mistake goes to stderr, never into the protocol.
    sys.stdout = sys.stderr
    log("started; tools: %s" % ", ".join(TOOL_NAMES))
    try:
        serve(stdin, stdout)
    except (KeyboardInterrupt, BrokenPipeError):
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
