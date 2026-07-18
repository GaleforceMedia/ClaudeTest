"""
End-to-end check of the persistence feature.

Walks the real flow - log a campaign, record a DHL export against it,
issue a client link, then run the exact aggregations the Insights page
performs. Streamlit itself isn't installed here, so this covers the data
path rather than the widgets; the aggregations are where the crashes
would be.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["KEP_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "e2e.db")

import pandas as pd  # noqa: E402
import storage  # noqa: E402

results = []


def check(label, cond, detail=""):
    results.append(cond)
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + (f"  [{detail}]" if detail else ""))


storage.init_db()

# --- 1. CSR logs campaigns -------------------------------------------------
print("\n1. campaigns logged")
storage.upsert_campaign("GRG-100", "Greggs", "Week 40", am="MS",
                        dispatch_date="2026-07-07", stores=200,
                        collation_hrs=9.0, status="🟢 Dispatched")   # Tuesday
storage.upsert_campaign("GRG-101", "Greggs", "Week 41", am="MS",
                        dispatch_date="2026-07-14", stores=180,
                        collation_hrs=11.0, status="🟢 Dispatched")  # Tuesday
storage.upsert_campaign("MPS-100", "Mamas & Papas", "Summer", am="JD",
                        dispatch_date="2026-07-09", stores=60,
                        collation_hrs=4.0, status="🟢 Dispatched")   # Thursday
check("three campaigns stored", len(storage.list_campaigns()) == 3)

# --- 2. DHL export recorded ------------------------------------------------
print("\n2. shipments recorded")
export = []
for i in range(20):
    export.append({
        "campaign_id": "GRG-100", "account": "F090402",
        "consignment": f"GRG100-{i}", "tracking_number": f"TRK{i}",
        "recipient": f"Greggs Store {i}", "postcode": f"NE{i} 1AA",
        "service": "Next Day", "status": "Delivered" if i < 15 else "In transit",
        "weight": 4.0, "parcels": 1, "cost": 5.34,
        # a few destinations repeatedly attract surcharges
        "surcharges": 7.50 if i in (3, 7) else 0.0,
        "co2_kg": 0.55, "dispatch_date": "2026-07-07",
    })
for i in range(8):
    export.append({
        "campaign_id": "MPS-100", "account": "F199630",
        "consignment": f"MPS100-{i}", "tracking_number": f"MTRK{i}",
        "recipient": f"M&P {i}", "postcode": f"LS{i} 2BB",
        "service": "Next Day Pre 12", "status": "Delivered",
        "weight": 12.0, "parcels": 2, "cost": 12.55,
        "surcharges": 15.00 if i == 0 else 0.0,
        "co2_kg": 1.2, "dispatch_date": "2026-07-09",
    })
written, _ = storage.record_shipments(export)
check("all shipments written", written == 28, f"n={written}")

# CSR re-uploads next morning to refresh statuses
for r in export:
    r["status"] = "Delivered"
storage.record_shipments(export)
check("re-upload didn't duplicate", len(storage.all_shipments()) == 28,
      f"n={len(storage.all_shipments())}")

# --- 3. client link --------------------------------------------------------
print("\n3. client link")
tok = storage.ensure_share_token("GRG-100")
camp = storage.get_campaign_by_token(tok)
check("link resolves to the right campaign", camp and camp["id"] == "GRG-100")

visible = storage.shipments_for_campaign(camp["id"])
check("client sees only their campaign's shipments", len(visible) == 20,
      f"n={len(visible)}")
check("client cannot see other clients' stores",
      not any("M&P" in (s.get("recipient") or "") for s in visible))

# --- 4. insights aggregations (the exact page logic) -----------------------
print("\n4. insights aggregations")
df = pd.DataFrame(storage.all_shipments())
df["client"] = df["client"].fillna("Unassigned")
df["dispatch_date"] = pd.to_datetime(df["dispatch_date"], errors="coerce")
for col in ("cost", "surcharges", "weight", "co2_kg"):
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
df["total"] = df["cost"] + df["surcharges"]

by_client = (df.groupby("client")
               .agg(Shipments=("id", "count"), Parcels=("parcels", "sum"),
                    Weight_kg=("weight", "sum"), Spend=("total", "sum"),
                    Surcharges=("surcharges", "sum"), CO2_kg=("co2_kg", "sum"))
               .sort_values("Spend", ascending=False))
check("by-client rollup runs", len(by_client) == 2, f"clients={list(by_client.index)}")
check("total spend ranks Greggs first on volume",
      by_client.index[0] == "Greggs",
      f"top={by_client.index[0]} £{by_client['Spend'].iloc[0]:.2f}")

# The insight the page is actually for: M&P ships a third as often but
# costs more per shipment. That only shows up once history accumulates.
by_client["Avg per shipment"] = by_client["Spend"] / by_client["Shipments"]
check("per-shipment cost exposes the pricier client",
      by_client.loc["Mamas & Papas", "Avg per shipment"]
      > by_client.loc["Greggs", "Avg per shipment"],
      f"M&P £{by_client.loc['Mamas & Papas', 'Avg per shipment']:.2f} "
      f"vs Greggs £{by_client.loc['Greggs', 'Avg per shipment']:.2f}")

charged = df[df["surcharges"] > 0]
worst = (charged.groupby(["recipient", "postcode"])
                .agg(Times=("id", "count"), Total=("surcharges", "sum"))
                .sort_values("Total", ascending=False).head(15).reset_index())
check("surcharge leaderboard runs", len(worst) == 3, f"rows={len(worst)}")
check("worst charge surfaces first",
      abs(worst["Total"].iloc[0] - 15.00) < 0.01)

timed = df.dropna(subset=["dispatch_date"])
series = (timed.set_index("dispatch_date")
               .groupby([pd.Grouper(freq="W"), "client"])["id"]
               .count().unstack(fill_value=0))
check("volume-over-time resample runs", not series.empty,
      f"shape={series.shape}")

# Collation load by weekday - the "are Tuesdays always overbooked" question.
# This is the fiddliest bit of the page, so exercise it exactly.
campaigns = pd.DataFrame(storage.list_campaigns())
campaigns["dispatch_date"] = pd.to_datetime(campaigns["dispatch_date"], errors="coerce")
campaigns["collation_hrs"] = pd.to_numeric(campaigns["collation_hrs"], errors="coerce").fillna(0)
campaigns = campaigns.dropna(subset=["dispatch_date"])
order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
campaigns["weekday"] = campaigns["dispatch_date"].dt.day_name()

per_day = (campaigns.groupby("weekday")
                    .agg(Campaigns=("id", "count"), Hours=("collation_hrs", "sum"))
                    .reindex(order).fillna(0))
avg = (campaigns.groupby("weekday")
                .apply(lambda g: g.groupby(g["dispatch_date"].dt.date)["collation_hrs"].sum().mean(),
                       include_groups=False)
                .reindex(order).fillna(0))
check("weekday capacity rollup runs", len(per_day) == 7)
check("Tuesday hours are highest", per_day["Hours"].idxmax() == "Tuesday",
      f"peak={per_day['Hours'].idxmax()} ({per_day['Hours'].max():.0f}h)")
check("average-per-day computed", avg["Tuesday"] > 0, f"tue avg={avg['Tuesday']:.1f}h")

# --- 5. revocation ---------------------------------------------------------
print("\n5. revocation")
storage.revoke_share_token("GRG-100")
check("revoked link stops resolving", storage.get_campaign_by_token(tok) is None)
check("shipment history survives revocation", len(storage.all_shipments()) == 28)

print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
