"""Tests for storage.py - run with: python3 tests/test_storage.py"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Point at a scratch DB before importing storage
_tmp = tempfile.mkdtemp()
os.environ["KEP_DB_PATH"] = os.path.join(_tmp, "test.db")

import storage  # noqa: E402

results = []


def check(label, cond, detail=""):
    results.append(cond)
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + (f"  [{detail}]" if detail else ""))


storage.init_db()

print("\ncampaigns")
storage.upsert_campaign("GRG-001", "Greggs", "Week 40", am="MS",
                        dispatch_date="2026-07-20", stores=120,
                        collation_hrs=6.0, status="🔴 Awaiting Artwork")
c = storage.get_campaign("GRG-001")
check("campaign saved", c is not None and c["client"] == "Greggs")

storage.upsert_campaign("GRG-001", "Greggs", "Week 40", am="MS",
                        dispatch_date="2026-07-20", stores=140,
                        collation_hrs=6.0, status="🟢 Dispatched")
c = storage.get_campaign("GRG-001")
check("upsert updates rather than duplicating",
      c["stores"] == 140 and c["status"] == "🟢 Dispatched",
      f"stores={c['stores']}")
check("only one row after upsert", len(storage.list_campaigns()) == 1)

print("\nshare tokens")
tok = storage.ensure_share_token("GRG-001")
check("token generated", bool(tok) and len(tok) > 30)
check("token is stable across calls", storage.ensure_share_token("GRG-001") == tok)
check("token resolves back to campaign",
      storage.get_campaign_by_token(tok)["id"] == "GRG-001")
check("bad token returns nothing", storage.get_campaign_by_token("nope") is None)
check("empty token returns nothing", storage.get_campaign_by_token("") is None)

storage.upsert_campaign("GRG-001", "Greggs", "Week 40", stores=140)
check("token survives a later campaign edit",
      storage.get_campaign("GRG-001")["share_token"] == tok)

storage.revoke_share_token("GRG-001")
check("revoked token stops working", storage.get_campaign_by_token(tok) is None)

print("\nshipments")
batch = [
    {"campaign_id": "GRG-001", "account": "F090402", "consignment": "C1",
     "tracking_number": "TRK1", "recipient": "Store A", "postcode": "B1 1AA",
     "service": "Next Day", "status": "In transit", "weight": 3.0,
     "parcels": 1, "cost": 5.34, "surcharges": 0.0, "co2_kg": 0.5,
     "dispatch_date": "2026-07-20"},
    {"campaign_id": "GRG-001", "account": "F090402", "consignment": "C2",
     "tracking_number": "TRK2", "recipient": "Store B", "postcode": "M1 1AA",
     "service": "Next Day", "status": "In transit", "weight": 8.0,
     "parcels": 2, "cost": 5.34, "surcharges": 7.50, "co2_kg": 1.1,
     "dispatch_date": "2026-07-20"},
    {"account": "F090402", "consignment": "", "recipient": "No consignment"},
]
written, skipped = storage.record_shipments(batch)
check("valid shipments written", written == 2, f"written={written}")
check("row without consignment skipped", skipped == 1)

# The important one: CSR re-uploads the same export to refresh tracking
batch[0]["status"] = "Delivered"
batch[1]["status"] = "Delivered"
storage.record_shipments(batch)
rows = storage.shipments_for_campaign("GRG-001")
check("re-upload does not duplicate", len(rows) == 2, f"rows={len(rows)}")
check("re-upload refreshes status",
      all(r["status"] == "Delivered" for r in rows))

# Same consignment ref on a different account is a different shipment
storage.record_shipments([{
    "account": "F181494", "consignment": "C1", "recipient": "PrintFlo store",
    "dispatch_date": "2026-07-20", "cost": 9.95, "surcharges": 0.0}])
check("same ref on another account kept separate",
      len(storage.all_shipments()) == 3, f"total={len(storage.all_shipments())}")

print("\nstats & history")
s = storage.stats()
check("shipment count", s["shipments"] == 3, f"n={s['shipments']}")
check("spend totals cost + surcharges",
      abs(s["spend"] - (5.34 + 5.34 + 7.50 + 9.95)) < 0.01, f"spend={s['spend']:.2f}")
check("surcharge total", abs(s["surcharges"] - 7.50) < 0.01)

hist = storage.all_shipments()
check("history joins client name onto shipments",
      any(r.get("client") == "Greggs" for r in hist))
check("unlinked shipment still returned", any(r.get("client") is None for r in hist))
check("date filter works", len(storage.all_shipments(since="2027-01-01")) == 0)

print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
