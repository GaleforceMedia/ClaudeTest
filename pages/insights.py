"""
Insights - what the accumulated history can tell you.

Reads the shipments and campaigns tables. Everything here is impossible
without persistence, which is why this page arrived at the same time as
storage.py.
"""
import datetime

import pandas as pd
import streamlit as st

from storage import all_shipments, init_db, list_campaigns, stats

st.set_page_config(page_title="Insights", page_icon="📈", layout="wide")

init_db()

st.title("📈 Insights")
st.write("Trends across everything the portal has recorded. The more campaigns you run through it, the more useful this gets.")

summary = stats()

if not summary["shipments"]:
    st.info(
        "No shipment history yet. Upload a DHL Dashboard Summary on the "
        "**Tracking Consolidator** page and tick *Save to history* — this page "
        "fills in from there."
    )
    st.stop()

# --- Headline numbers -----------------------------------------------------
m1, m2, m3, m4 = st.columns(4)
m1.metric("Campaigns", f"{summary['campaigns']:,}")
m2.metric("Shipments", f"{summary['shipments']:,}")
m3.metric("Carrier spend", f"£{summary['spend']:,.2f}")
m4.metric("Of which surcharges", f"£{summary['surcharges']:,.2f}")

st.divider()

# --- Load + prepare -------------------------------------------------------
df = pd.DataFrame(all_shipments())
df["client"] = df["client"].fillna("Unassigned")
df["dispatch_date"] = pd.to_datetime(df["dispatch_date"], errors="coerce")
for col in ("cost", "surcharges", "weight", "co2_kg"):
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
df["total"] = df["cost"] + df["surcharges"]

# Optional date window
dated = df.dropna(subset=["dispatch_date"])
if not dated.empty:
    lo = dated["dispatch_date"].min().date()
    hi = dated["dispatch_date"].max().date()
    if lo < hi:
        picked = st.date_input("Date range", value=(lo, hi), min_value=lo, max_value=hi)
        if isinstance(picked, tuple) and len(picked) == 2:
            start, end = (pd.Timestamp(p) for p in picked)
            mask = df["dispatch_date"].between(start, end) | df["dispatch_date"].isna()
            df = df[mask]

tab_client, tab_surcharge, tab_volume, tab_capacity = st.tabs(
    ["By client", "Surcharges", "Volume over time", "Collation load"]
)

# --- By client ------------------------------------------------------------
with tab_client:
    by_client = (
        df.groupby("client")
          .agg(Shipments=("id", "count"),
               Parcels=("parcels", "sum"),
               Weight_kg=("weight", "sum"),
               Spend=("total", "sum"),
               Surcharges=("surcharges", "sum"),
               CO2_kg=("co2_kg", "sum"))
          .sort_values("Spend", ascending=False)
    )
    by_client["Avg per shipment"] = (
        by_client["Spend"] / by_client["Shipments"].replace(0, pd.NA)
    ).fillna(0)

    st.bar_chart(by_client["Spend"], height=280)
    st.dataframe(
        by_client.reset_index(),
        use_container_width=True, hide_index=True,
        column_config={
            "Spend": st.column_config.NumberColumn("Spend", format="£%.2f"),
            "Surcharges": st.column_config.NumberColumn("Surcharges", format="£%.2f"),
            "Avg per shipment": st.column_config.NumberColumn("Avg per shipment", format="£%.2f"),
            "Weight_kg": st.column_config.NumberColumn("Weight (kg)", format="%.1f"),
            "CO2_kg": st.column_config.NumberColumn("CO2e (kg)", format="%.1f"),
        },
    )

# --- Surcharges -----------------------------------------------------------
with tab_surcharge:
    st.write("Surcharges are the cost that shouldn't be there. This shows where they're concentrated.")

    charged = df[df["surcharges"] > 0]
    if charged.empty:
        st.success("No surcharges recorded in this period.")
    else:
        pct = len(charged) / len(df) * 100
        s1, s2, s3 = st.columns(3)
        s1.metric("Shipments surcharged", f"{len(charged):,}", f"{pct:.1f}% of all")
        s2.metric("Total surcharged", f"£{charged['surcharges'].sum():,.2f}")
        s3.metric("Worst single charge", f"£{charged['surcharges'].max():,.2f}")

        st.bar_chart(
            charged.groupby("client")["surcharges"].sum().sort_values(ascending=False),
            height=260,
        )

        st.write("**Most surcharged destinations** — a postcode appearing repeatedly usually means a dimension or weight recorded wrong at booking.")
        worst = (
            charged.groupby(["recipient", "postcode"])
                   .agg(Times=("id", "count"), Total=("surcharges", "sum"))
                   .sort_values("Total", ascending=False)
                   .head(15)
                   .reset_index()
        )
        st.dataframe(
            worst, use_container_width=True, hide_index=True,
            column_config={"Total": st.column_config.NumberColumn("Total", format="£%.2f")},
        )

# --- Volume over time -----------------------------------------------------
with tab_volume:
    timed = df.dropna(subset=["dispatch_date"])
    if timed.empty:
        st.info("No dispatch dates recorded yet.")
    else:
        grain = st.radio("Group by", ["Week", "Month"], horizontal=True)
        freq = "W" if grain == "Week" else "MS"
        series = (
            timed.set_index("dispatch_date")
                 .groupby([pd.Grouper(freq=freq), "client"])["id"]
                 .count().unstack(fill_value=0)
        )
        st.line_chart(series, height=300)

        spend = (
            timed.set_index("dispatch_date")
                 .groupby(pd.Grouper(freq=freq))["total"].sum()
        )
        st.write("**Carrier spend over the same period**")
        st.bar_chart(spend, height=240)

# --- Collation load -------------------------------------------------------
with tab_capacity:
    st.write("Which days your collation hours actually land on — the answer to whether Tuesdays are always overbooked.")

    campaigns = pd.DataFrame(list_campaigns())
    if campaigns.empty or "dispatch_date" not in campaigns:
        st.info("No campaigns recorded yet.")
    else:
        campaigns["dispatch_date"] = pd.to_datetime(campaigns["dispatch_date"], errors="coerce")
        campaigns["collation_hrs"] = pd.to_numeric(campaigns["collation_hrs"], errors="coerce").fillna(0)
        campaigns = campaigns.dropna(subset=["dispatch_date"])

        if campaigns.empty:
            st.info("No campaigns have a dispatch date set.")
        else:
            order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            campaigns["weekday"] = campaigns["dispatch_date"].dt.day_name()

            per_day = (
                campaigns.groupby("weekday")
                         .agg(Campaigns=("id", "count"), Hours=("collation_hrs", "sum"))
                         .reindex(order).fillna(0)
            )
            per_day["Avg hrs per dispatch day"] = (
                campaigns.groupby("weekday")
                         .apply(lambda g: g.groupby(g["dispatch_date"].dt.date)["collation_hrs"].sum().mean(),
                                include_groups=False)
                         .reindex(order).fillna(0)
            )

            st.bar_chart(per_day["Avg hrs per dispatch day"], height=260)

            MAX_DAILY_HOURS = 16.0
            over = per_day[per_day["Avg hrs per dispatch day"] > MAX_DAILY_HOURS]
            if not over.empty:
                st.warning(
                    "On average, these days already exceed the "
                    f"{MAX_DAILY_HOURS:.0f}-hour collation limit: "
                    + ", ".join(over.index) + ". Worth moving dispatch dates or adding capacity."
                )

            st.dataframe(
                per_day.reset_index().rename(columns={"index": "Weekday"}),
                use_container_width=True, hide_index=True,
                column_config={
                    "Hours": st.column_config.NumberColumn("Total hours", format="%.1f"),
                    "Avg hrs per dispatch day": st.column_config.NumberColumn("Avg hrs/day", format="%.1f"),
                },
            )

st.divider()
st.caption(f"Covering {len(df):,} shipments. Generated {datetime.date.today().strftime('%d %B %Y')}.")
