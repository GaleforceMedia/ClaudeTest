"""
Read-only delivery tracking, shown to a client via a share link.

Reached only as ?share=<token>. app.py resolves the token BEFORE building
the navigation, and when a valid token is present it registers this page
as the only page in the session - so there is no menu and no route to
any internal page.
"""
import streamlit as st

from storage import get_campaign_by_token, shipments_for_campaign
from utils import BRANDING, DEFAULT_BRAND, KEP_BLUE, get_base64_image

st.set_page_config(
    page_title="Delivery tracking",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="collapsed",
)

token = st.query_params.get("share")
campaign = get_campaign_by_token(token)

# Belt and braces. app.py already gates this, but a page should never
# assume it was reached the way it was meant to be.
if not campaign:
    st.error("This tracking link isn't valid. It may have expired — please ask your KEP contact for a new one.")
    st.stop()

shipments = shipments_for_campaign(campaign["id"])

# --- Header ---------------------------------------------------------------
logo = get_base64_image("logo.svg")
logo_html = (
    f"<img src='{logo}' alt='KEP Print Group' style='max-height:44px;'>"
    if logo else "<span style='color:#fff;font-size:20px;font-weight:bold;'>KEP Print Group</span>"
)
st.markdown(
    f"""
    <div style="background:{KEP_BLUE};padding:20px 28px;border-radius:8px;
                display:flex;justify-content:space-between;align-items:center;margin-bottom:24px;">
        {logo_html}
        <div style="color:#fff;text-align:right;">
            <div style="font-size:18px;font-weight:bold;">{campaign['client']}</div>
            <div style="font-size:14px;opacity:.85;">{campaign['name']}</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if not shipments:
    st.info("This campaign hasn't been dispatched yet. Tracking will appear here as soon as it ships.")
    st.stop()

# --- Summary --------------------------------------------------------------
delivered = sum(1 for s in shipments if str(s.get("status", "")).lower() == "delivered")
in_transit = len(shipments) - delivered

c1, c2, c3 = st.columns(3)
c1.metric("Destinations", len(shipments))
c2.metric("Delivered", delivered)
c3.metric("In transit", in_transit)

if delivered:
    st.progress(delivered / len(shipments))

st.divider()

# --- Filter + table -------------------------------------------------------
query = st.text_input("Find a store", placeholder="Store name or postcode")

rows = shipments
if query:
    q = query.lower()
    rows = [
        s for s in shipments
        if q in str(s.get("recipient", "")).lower()
        or q in str(s.get("postcode", "")).lower()
    ]
    if not rows:
        st.warning(f"No destinations matching “{query}”.")

table = [
    {
        "Store": s.get("recipient") or "—",
        "Postcode": s.get("postcode") or "—",
        "Service": s.get("service") or "—",
        "Parcels": s.get("parcels") or 1,
        "Status": s.get("status") or "Awaiting update",
        "Expected": s.get("eta") or "—",
        "Track": (
            f"https://www.dhl.com/gb-en/home/tracking.html?tracking-id={s['tracking_number']}&submit=1"
            if s.get("tracking_number") else None
        ),
    }
    for s in rows
]

st.dataframe(
    table,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Track": st.column_config.LinkColumn("Track", display_text="Track parcel"),
        "Parcels": st.column_config.NumberColumn("Parcels", format="%d"),
    },
)

st.caption(
    "Status comes directly from the carrier and updates as parcels move. "
    "Questions about this delivery? Contact your KEP account manager."
)
