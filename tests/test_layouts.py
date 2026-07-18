"""
Smoke test for the three pick-list engines.

fpdf2 isn't installable in this sandbox (no network), so FPDF is stubbed
with a recorder. That's fine - the change under test is in the *parsing*,
so what we care about is how many store pages get emitted and with what
headings.

The key assertion: two stores sharing a name must produce TWO pick lists.
Before the fix they were dict keys, so one silently vanished.
"""
import os
import sys
import types
import pandas as pd

# ---- stub fpdf ----------------------------------------------------
pages = []


class FakePDF:
    def __init__(self, *a, **k):
        self.current = None

    def add_page(self):
        self.current = []
        pages.append(self.current)

    def cell(self, *a, **k):
        t = k.get("txt") or k.get("text")
        if t is None and len(a) > 2:
            t = a[2]
        if isinstance(t, str) and t.strip() and self.current is not None:
            self.current.append(t.strip())

    def multi_cell(self, *a, **k):
        self.cell(*a, **k)

    def output(self, *a, **k):
        return b""

    def get_y(self, *a, **k):
        return 10.0

    def get_x(self, *a, **k):
        return 10.0

    def __getattr__(self, name):
        return lambda *a, **k: None


fake = types.ModuleType("fpdf")
fake.FPDF = FakePDF
sys.modules["fpdf"] = fake

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from mp_layout import generate_picklists, extract_dhl_data   # noqa: E402
from th_layout import generate_th_picklists                  # noqa: E402
from cu_layout import generate_cu_picklists                  # noqa: E402


def reset():
    pages.clear()


def headings():
    """Every string written to any page, flattened."""
    return [t for page in pages for t in page]


results = []


def check(label, condition, detail=""):
    results.append((label, condition, detail))
    print(f"  {'PASS' if condition else 'FAIL'}  {label}" + (f"  [{detail}]" if detail else ""))


# ================= M&P =================
# Layout: job row=1, size row=4, code row=5, versions row=6, stores from row 7
# FAO=B(1) addr2=D(3) addr3=F(5) addr4=G(6) postcode=H(7) store=I(8) products from J(9)
print("\nM&P layout")
rows = [[None] * 11 for _ in range(7)]
rows[1][9] = "JOB100"; rows[1][10] = "JOB200"
rows[4][9] = "A1";     rows[4][10] = "A2"
rows[5][9] = "CODE-X"; rows[5][10] = "CODE-Y"
rows[6][9] = "v1";     rows[6][10] = "v2"
# two stores with the SAME name, plus one with zero qty that must be skipped
rows.append([None, "Mgr", None, "1 High St", None, "Town", "Shire", "B1 1AA", "Birmingham", 5, 0])
rows.append([None, "Mgr", None, "2 Low Rd",  None, "Town", "Shire", "B2 2BB", "Birmingham", 3, 1])
rows.append([None, "Mgr", None, "9 Nil Way", None, "Town", "Shire", "B9 9ZZ", "Emptyville", 0, 0])
pd.DataFrame(rows).to_excel("/tmp/mp.xlsx", header=False, index=False)

reset()
generate_picklists("/tmp/mp.xlsx", "/tmp/mp.pdf", campaign_title="Test Campaign")
h = headings()
check("duplicate store names both produce a pick list",
      sum("Birmingham" in x for x in h) == 2,
      f"found {sum('Birmingham' in x for x in h)}")
check("store with all-zero qty is skipped",
      not any("Emptyville" in x for x in h))

dhl = extract_dhl_data("/tmp/mp.xlsx", "REF1", "3", 1, "01/01/2026")
check("DHL export includes both same-named stores", len(dhl) == 2, f"rows={len(dhl)}")
check("DHL export excludes the zero-qty store",
      all("Emptyville" not in r["Full Name"] for r in dhl))

# ================= Tim Hortons =================
# type row=1, code row=2, spec row=4, stores from row 5
# postcode=F(5), store=H(7), tier=I(8), products from J(9)
print("\nTim Hortons layout")
rows = [[None] * 10 for _ in range(5)]
rows[1][9] = "A BOARDS"
rows[2][9] = "C4-ABA1-MANGO"
rows[4][9] = "A1 1pp 3mm Foamex"
rows.append([None, None, None, None, None, "LS1 1AA", None, "Leeds Central", 1, 4])
rows.append([None, None, None, None, None, "LS2 2BB", None, "Leeds Central", 2, 6])
pd.DataFrame(rows).to_excel("/tmp/th.xlsx", header=False, index=False)

reset()
generate_th_picklists("/tmp/th.xlsx", "/tmp/th.pdf")
h = headings()
check("duplicate store names both produce a pick list",
      sum("LEEDS CENTRAL" in x.upper() for x in h) == 2,
      f"found {sum('LEEDS CENTRAL' in x.upper() for x in h)}")

# ================= Craft Union =================
# job row=1, title row=2, stores from row 3
# bun=A(0), pub=B(1), postcode=G(6), products from I(8)
print("\nCraft Union layout")
rows = [[None] * 10 for _ in range(3)]
rows[1][8] = "J500"
rows[2][8] = "Poster A2"
rows.append(["101", "The Red Lion", None, None, None, None, "M1 1AA", None, 2])
rows.append(["102", "The Red Lion", None, None, None, None, "M2 2BB", None, 7])
pd.DataFrame(rows).to_excel("/tmp/cu.xlsx", header=False, index=False)

reset()
generate_cu_picklists("/tmp/cu.xlsx", "/tmp/cu.pdf", campaign_title="CU Test")
h = headings()
check("duplicate pub names both produce a pick list",
      sum("RED LION" in x.upper() for x in h) == 2,
      f"found {sum('RED LION' in x.upper() for x in h)}")
check("BUN numbers not mangled to floats",
      any("101" in x for x in h) and not any("101.0" in x for x in h))

# ================= summary =================
failed = [r for r in results if not r[1]]
print(f"\n{len(results) - len(failed)}/{len(results)} passed")
sys.exit(1 if failed else 0)
