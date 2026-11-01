# Glossary for report readers

Plain meanings of the words in `report.md`. The full rules are in
[usage.md](usage.md) and [report-schema.md](report-schema.md). To see the
words in place, read the [sample report](../examples/sample-report.md),
made from the made-up demo inventory.

## The lists

**Past end of life.** The item's end-of-life date is on or before the
checked-on date at the top of the report. Each item needs a decision:
replace, upgrade, retire, or request risk acceptance.

**Ends soon** (the report heading is "Ends within the lookahead window").
The item's end-of-life date falls after the checked-on date and inside the
window, which is 12 months unless you set `--lookahead-months`.

**Dates disagree.** Two dates for the item do not agree: your export's own
date and the endoflife.date date differ, rows of one item carry different
export dates, endoflife.date has no date to compare, a golden source
has passed its review-by date, or a golden source says to use the export
date and the export has no usable one. The ITAM lead settles which date to use.
Nothing is settled for you.

**Couldn't match.** The name and version did not map to a known product
and cycle, so the tool claims no date for the item. The line under each
item gives the reason: no known product fits the name (`NO_ALIAS`), the
product is known but no cycle fits the version (`NO_CYCLE`), no version
was given (`NO_VERSION`), or the name fits more than one product
(`AMBIGUOUS`). Parts with a parent are listed in their own section. What
to do with these is in step 9, "Handle "Couldn't match"", of
[sop.md](sop.md).

**Names to review.** Rows the tool left unmatched on purpose. The name
looks like a product in the catalog, but there is not enough evidence to
match it to one support line, often because the row has no publisher.
It is not a finding, and no cycle, date or state is shown. A product is
shown only when the version fits more than one support line (Internet
Explorer 11 on desktop, Server, LTSB or LTSC Windows). To settle one, add
a publisher that names the vendor, ask for a curated alias, or record that
it is a different product; for Internet Explorer 11, check which Windows
it runs on. These rows are also counted under "Couldn't
match". See "Names to review" in [usage.md](usage.md).

**In CISA KEV, past or near end of life.** The item is past end of life or
ends within the window, and its vendor and product appear in the CISA
Known Exploited Vulnerabilities catalog (KEV). The report prints this
line on each one: "The vendor and product appear in CISA KEV. This does
not mean your version is affected." KEV is matched on vendor and product
only, never on version. A person checks the version against the KEV
entries and decides the priority. For an item past or near end of life,
no KEV line means "no match under the tool's rules", not "known safe".

**Accepted risk.** The item is listed in your exceptions file and the
exception has not expired. The tool lists it and does not confirm the
sign-off.

**Ownerless.** The export names no owner for the item. It cannot be
actioned until an owner is named.

**Golden source overrides.** Items whose state changed because a golden
source (below) chose a different date.

## Words on each item

**Product matched by a curated alias** and **Product matched by product
title**. How the tool found the product for an item it matched: an alias
the maintainer keeps, or the name equals the product's title. **Product
known; version not matched.** On a "Couldn't match" item: the tool knows
the product, but no single cycle was decided for the version (or no
version was given), so no date is claimed.

**Inventory rows** and **Count (from your file)**. "Inventory rows: N" is
how many rows of your export made this item: rows in the export, not
installs or machines. "Count (from your file): N" is the sum of your
file's count column for those rows. The tool does not check it, and it
only sets the order of items, largest first. Neither number is a licence
position, and neither is a count of installs the tool found.

**Classification.** What kind of item this is. There are four classes,
and they are this tool's own terms, not terms from a standard:

- **Governable**: a standalone application, server, database, operating
  system, browser, security agent or directly used developer tool, and
  standalone runtimes such as a JDK, .NET, Node.js or Python.
- **Component**: a library, redistributable, driver, language pack,
  operating system patch, font, codec, extension, plugin, `lib*` or `-dev`
  package, with no known parent.
- **Bundle member**: a part with a named parent, such as a suite member, a
  runtime inside an app, a driver pack, or an operating system patch of
  the operating system item. A bundle member may show its parent's date under "Parent's
  date (inherited, not this item's own)". That date is the parent's. It
  never puts the part on "Past end of life" or "Ends soon".
- **Unknown**: the tool cannot tell. This is a valid answer and the
  default.

## Your files

**Support record.** A row in your support-records file, such as an
extended-support contract, shown beside the vendor's dates: "A support
record is listed in your file". It helps you weigh paying for extended
support against migrating, and plan renewals. A record never changes an
item's state or lists. The tool does not check that a record was paid
for or is current. "Not matched to a dated item in this inventory" is not
proof that a product is not in use, because software missing from the
export may still be in use.

**Golden source.** A row in your golden-sources file that says which
end-of-life date is right for a product (the endoflife.date date, your
export's date, or a date you give) and when to review that choice. After
its review-by date, the item goes back on "Dates disagree".

**Exception.** A row in your exceptions file that records accepted risk:
compensating controls, a risk owner, an approver who is not the person
who asked, an expiry date and your reference. After the expiry date the
item shows "Decision needed: The risk exception has expired."

## Data age

**KEV data "not current".** The KEV snapshot the run used is more than 7
days older than the checked-on date, or is dated more than a day after
it. The report then says "KEV overlay is not current." and gives the snapshot's
age. The KEV list may be out of date: an empty "In CISA KEV" section then
reads "None listed. KEV overlay is not current, so this does not show
there are none." A snapshot more than 3 days old already gives a warning.
What to do is in [quick-start.md](quick-start.md).

## The desktop chat app server

These words appear in [mcp-setup.md](mcp-setup.md).

**MCP server.** A small program that a chat app starts on your computer
to give the assistant extra tools. MCP (Model Context Protocol) is the
standard way chat apps do this. This repo's one is `swlc_mcp.py`.

**Tool.** One action the assistant can ask the server to do. This server
has two: `preflight` and `check_counts`.

**stdio.** Short for standard input and output. The chat app and the
server talk by passing lines of text through them, on your computer,
with no network.

**Allow-list.** A list of the only things let through. The server
returns only output lines it knows (fixed labels and numbers) and drops
everything else, so item IDs and file content never reach the assistant.
