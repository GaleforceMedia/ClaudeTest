# KEP CSR Portal

Internal Streamlit tools for KEP Print Group — pick lists, dispatch paperwork,
courier batch files, campaign scheduling, stock control and CO2 reporting.

---

## Running it locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then open http://localhost:8501.

## Running the tests

```bash
python3 tests/test_layouts.py
```

Covers the three pick-list engines (M&P, Tim Hortons, Craft Union): store
parsing, zero-quantity skipping, DHL row extraction, and the duplicate-store
regression described below.

---

## ⚠️ Read this before you host it

### 1. Three pages write to CSV files, and that data is not safe

`Inventory Allocator`, `Campaign Master Schedule` and `Greggs Store Orders`
save their state to CSV files next to the code (`live_inventory.csv`,
`campaign_database.csv`, `greggs_orders_db.csv`).

**On any host with an ephemeral filesystem — Streamlit Community Cloud, most
container platforms, Heroku — those files are wiped every time the app
restarts, redeploys, or goes to sleep.** Your entire warehouse stock count and
campaign schedule silently reset to empty. This is the single biggest risk in
the project and it will bite you the first time you push an update.

Options, cheapest first:

| Option | Effort | Notes |
|---|---|---|
| **Supabase / Neon** (hosted Postgres) | Low | Free tier is plenty. Swap the `load_*`/`save_*` functions for SQL. Best all-round choice. |
| **Google Sheets** via `gspread` | Low | Non-technical staff can eyeball and fix data directly, which suits a warehouse. Slower, rate-limited. |
| **SQLite on a persistent disk** | Medium | Only works on hosts that give you a real volume (Railway, Fly.io, a VM). Not Community Cloud. |
| **Azure/S3 blob** | Medium | Fine if you're already in a cloud tenancy. |

The three save functions are already isolated and each go through
`utils.locked_save()`, so switching backends means changing three small
functions, not rewriting pages.

### 2. Concurrency

Multiple CSRs using the app at once used to be able to clobber each other's
saves — page loads the whole CSV, edits in memory, writes the whole file back.
Two people saving within the same few seconds meant one person's work vanished.

Saves now go through a file lock (`utils.locked_save`), which closes the
corrupt-file window. It does **not** fix last-writer-wins on the same row —
a proper database with row-level updates does. Treat the lock as a seatbelt,
not a solution.

### 3. There's no access control by default

Anything on a public URL is public. A shared-password gate is built in but
**off** unless you configure it:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# edit it and set app_password = "..."
```

On Streamlit Community Cloud, paste the same content into
**App settings → Secrets**. `secrets.toml` is gitignored — never commit it.

For proper per-user logins (who booked that stock out?), look at Streamlit's
native OIDC auth (`st.login`) against your Microsoft 365 tenancy — since
you're already a Microsoft shop, that gets you real named accounts.

---

## Project layout

```
app.py                  entrypoint + navigation menu + shared header
utils.py                shared branding, image encoder, login gate, save lock
mp_layout.py            Mamas & Papas pick list PDF + DHL extraction
th_layout.py            Tim Hortons pick list PDF
cu_layout.py            Craft Union pick list PDF
pages/                  one file per screen
tests/test_layouts.py   regression tests for the three PDF engines
KEP OCT 2025.xlsx       material price list (Purchase Requisition reads this)
```

Navigation lives in `app.py`. To add a page: drop the file in `pages/`, then
add one `st.Page(...)` line under the right heading. Page titles, icons and
ordering are all set there now, so filenames stay clean.

---

## What changed in this cleanup

**Fixed**

- **Duplicate store names silently lost pick lists.** All three engines keyed
  stores by name in a dict, so two stores sharing a name produced *one* pick
  list — the second overwrote the first and that store simply never got picked.
  For Craft Union (pubs — "The Red Lion" etc.) this was very likely happening
  in production. Now keyed by position. Covered by a regression test.
- **`streamlit` was missing from `requirements.txt`** entirely. It worked
  locally because it was already installed; a clean deploy would have failed
  outright.
- **Page filenames were corrupted** — emoji in the names had been mangled into
  literal text like `1_#L01f4dd_Purchase Req.py`, which Streamlit was showing
  verbatim in the sidebar. Renamed to plain ASCII; labels/icons now come from
  `st.navigation` instead.
- **Requisition forms were hardcoded to one person's name.** Every POR printed
  "Matt Gale" as requester regardless of who made it. Now a field.
- **Pallet quotes silently defaulted to Zone 2.** Typing a real postcode
  (`CV34 6TT`) instead of a bare area code didn't match the zone map and fell
  through to Zone 2 with no warning — under-quoting London/Home Counties jobs.
  Now parses the area code and warns loudly when a zone isn't recognised.
- **`save_db` could crash on the Campaign Schedule** when the date column
  arrived as plain dates rather than datetimes.
- Spreadsheet and courier-export text is now HTML-escaped before being written
  into generated HTML reports — an `&` or `<` in a store name used to break the
  page layout.
- Fixed an invalid regex escape (`'\.0'` → `r'\.0'`) that emitted a warning and
  will break on a future Python.
- `greggs_orders.save_db` no longer mutates the caller's DataFrame.

**Cleaned up**

- ~60 lines of branding config and the base64 image helper were copy-pasted
  across pages; both now live in `utils.py`.
- Added `.gitignore` (the generated CSVs and `__pycache__` were being
  committed), `.streamlit/config.toml` for the KEP blue theme, and this README.
- The blue KEP header now renders on every page, not just Home.

---

## Ideas worth doing next

Roughly in order of payback:

1. **Move the three CSV pages to a real database.** See the table above. This
   is the one that stops you losing data.
2. **Barcode/QR on pick lists.** Print the job number as a barcode; a warehouse
   scanner then confirms picks instead of someone ticking a box. Biggest
   accuracy win available and `fpdf2` can render them directly.
3. **Reuse the Dispatch Calculator's rates in the Invoice Checker.** You
   already hold DHL rate cards in one page and actual invoiced costs in
   another. Comparing them would show you exactly where you're being
   overbilled, rather than only flagging surcharges.
4. **A "campaign pack" button.** One click producing pick lists + DHL batch
   file + labels for a campaign, instead of visiting three pages and
   re-uploading the same spreadsheet each time.
5. **Validate spreadsheets on upload.** The layout engines assume fixed row and
   column positions. If a client shifts a column, you get a wrong pick list
   rather than an error. A quick "does row 2 look like job numbers?" check
   before generating would catch it.
6. **Log allocations, don't just decrement.** Inventory currently subtracts
   stock but doesn't record who took what for which job, so there's no audit
   trail and no way to undo a mistake.
7. **Carbon factors need sourcing.** The CO2 numbers are adjustable sliders
   with invented defaults. If these reports go to clients as ESG evidence,
   base the factors on DEFRA's published freight figures and cite them on the
   report — otherwise the numbers won't survive scrutiny.
