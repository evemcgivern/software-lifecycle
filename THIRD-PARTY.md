# Third-party material

## endoflife.date

Source: https://github.com/endoflife-date/endoflife.date

Used for:

- `tests/fixtures/upstream/*.md`: trimmed copies of four product files,
  taken from the commit named in `tests/fixtures/upstream/NOTICE.txt`. Page
  text is removed. See `tests/fixtures/upstream/NOTICE.txt`.
- `data/eol/*.json`: release cycle identifiers and dates read from the
  endoflife.date product files at the commit named as `upstream_commit` in
  `data/manifest.json`. Product descriptions are
  not included.

Licence of the repository (MIT):

    Copyright 2020 endoflife.date contributors

    Permission is hereby granted, free of charge, to any person obtaining a
    copy of this software and associated documentation files (the
    "Software"), to deal in the Software without restriction, including
    without limitation the rights to use, copy, modify, merge, publish,
    distribute, sublicense, and/or sell copies of the Software, and to
    permit persons to whom the Software is furnished to do so, subject to
    the following conditions:

    The above copyright notice and this permission notice shall be included
    in all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
    OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
    MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
    IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
    CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
    TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
    SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

## CISA Known Exploited Vulnerabilities catalog

Source: https://www.cisa.gov/known-exploited-vulnerabilities-catalog

Used for `data/kev.json` (and `kev.json` in data releases): CVE id,
vendor, product and date added only. The bundled copy's catalog version is
`kev_catalog_version` in `data/manifest.json`. CISA publishes the catalog under CC0 1.0
(https://github.com/cisagov/kev-data). The feed itself carries no licence
field, so `refresh_data.py` writes the note `"license": "CC0 1.0"` into
`kev.json`.
