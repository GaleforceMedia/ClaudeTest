import streamlit as st

from storage import get_campaign_by_token, init_db
from utils import KEP_BLUE, get_base64_image, require_login

st.set_page_config(page_title="KEP Portal", page_icon="🏠", layout="wide")

init_db()


# --- CLIENT MODE ----------------------------------------------------------
# Resolved BEFORE the internal navigation is built. When a valid share
# token is present, the client tracking page is the only page registered
# for this session, so there is no menu and no route to anything internal.
#
# NOTE: this protects the client from wandering in. It does NOT protect
# the internal app from someone who simply drops the ?share= parameter -
# that's what require_login() below is for. Turn the password on before
# you send a link to anyone outside KEP.
_token = st.query_params.get("share")
if _token and get_campaign_by_token(_token):
    st.navigation([
        st.Page("pages/client_tracking.py", title="Delivery tracking", default=True)
    ]).run()
    st.stop()


# --- SHARED BLUE HEADER (now shown on every page, not just Home) ---
def render_header():
    base64_svg = get_base64_image("logo.svg")
    if base64_svg:
        header_html = f"""
        <div style="background-color: {KEP_BLUE}; padding: 30px; border-radius: 8px; text-align: center; margin-bottom: 30px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <img src="data:image/svg+xml;base64,{base64_svg}" alt="KEP Print Group Logo" style="max-height: 70px;">
        </div>
        """
    else:
        header_html = f"""
        <div style="background-color: {KEP_BLUE}; padding: 30px; border-radius: 8px; text-align: center; margin-bottom: 30px;">
            <h1 style="color: white; margin: 0; font-family: Arial, sans-serif;">KEP Print Group</h1>
        </div>
        """
    st.markdown(header_html, unsafe_allow_html=True)


render_header()

# Password gate: no-op unless an `app_password` secret is set (see README.md).
require_login()

# --- NAVIGATION ---
# Filenames no longer carry the page number/icon/title - that's all defined
# here in one place instead, which is also what fixed the garbled sidebar
# labels (the old filenames had emoji that got mangled into things like
# "#L01f4dd" at some point, and Streamlit was showing that text verbatim).
pages = {
    "Overview": [
        st.Page("pages/home.py", title="Home", icon="🏠", default=True),
        st.Page("pages/insights.py", title="Insights", icon="📈"),
    ],
    "Dispatch & Shipping": [
        st.Page("pages/pick_lists.py", title="Pick Lists", icon="📦"),
        st.Page("pages/label_maker.py", title="Label Maker", icon="🏷️"),
        st.Page("pages/dhl_batchfile.py", title="DHL Batch Maker", icon="✉️"),
        st.Page("pages/dhl_invoice_checker.py", title="DHL Invoice Checker", icon="🧾"),
        st.Page("pages/tracking_consolidator.py", title="Tracking Consolidator", icon="🚚"),
        st.Page("pages/dispatch_calculator.py", title="Dispatch Calculator", icon="🧮"),
        st.Page("pages/carbon_engine.py", title="Carbon Impact Engine", icon="🌱"),
    ],
    "Campaigns & Client Orders": [
        st.Page("pages/campaign_schedule.py", title="Campaign Master Schedule", icon="📅"),
        st.Page("pages/greggs_orders.py", title="Greggs Store Orders", icon="🥐"),
        st.Page("pages/printflo_callofs.py", title="PrintFlo Call-Offs", icon="📊"),
        st.Page("pages/printflo_spk.py", title="PrintFlo (SPK) Pick Lists", icon="🖨️"),
        st.Page("pages/collation_machine.py", title="Collation Machine", icon="⚙️"),
    ],
    "Warehouse & Purchasing": [
        st.Page("pages/inventory_allocator.py", title="Inventory Allocator", icon="🏬"),
        st.Page("pages/purchase_req.py", title="Purchase Requisition", icon="📝"),
    ],
}

pg = st.navigation(pages)
pg.run()
