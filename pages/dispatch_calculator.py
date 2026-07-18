import streamlit as st
import pandas as pd
import math
import re

st.set_page_config(page_title="Dispatch Calculator", page_icon="🧮", layout="wide")

# --- KEP BRANDING & CSS ---
st.markdown("""
    <style>
    .stButton>button { background-color: #000000; color: white; border-radius: 4px; font-weight: bold; padding: 10px; width: 100%; border: none; }
    .stButton>button:hover { background-color: #333333; color: white; }
    .metric-card { background-color: #f8f9fa; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; text-align: center; margin-bottom: 15px; }
    .price-text { color: #004B87; font-size: 32px; font-weight: bold; margin: 0; }
    .working-out-box { background-color: #e9ecef; padding: 15px; border-radius: 5px; font-family: monospace; font-size: 14px; color: #333; }
    </style>
    """, unsafe_allow_html=True)

st.title("🧮 KEP Dispatch Calculator")
st.write("Input the raw data. The system will convert units, determine the sizing, and calculate the exact KEP sell price.")
st.divider()

# ==========================================
# 1. RATE CARDS & LOGIC DICTIONARIES
# ==========================================

# DHL Base Rates (Zone A assumed standard for this logic, easily expandable)
DHL_RATES = {
    "Next Working Day": {"base": 5.3354, "per_kg_over_20": 0.3399},
    "Next Working Day Pre 12": {"base": 12.5454, "per_kg_over_20": 0.3399},
    "Next Working Day Pre 10": {"base": 12.4321, "per_kg_over_20": 0.3399},
    "Next Working Day Pre 9": {"base": 15.1616, "per_kg_over_20": 0.3399},
    "Saturday": {"base": 15.0000, "per_kg_over_20": 0.3399},        
    "Saturday Pre 12": {"base": 20.0000, "per_kg_over_20": 0.3399}, 
}

# Pallet Postcode Mapping (Zone 2, 3, 4, 5, 6)
PALLET_POSTCODES = {
    "Zone 2": ["B", "BB", "BD", "BL", "BS", "CB", "CH", "CV", "CW", "DE", "DN", "DY", "HD", "HG", "HP", "HX", "L", "LE", "LS", "LU", "M", "MK", "NG", "NN", "OL", "PR", "S", "SK", "ST", "TF", "WA", "WF", "WN", "WR", "WS", "WV"],
    "Zone 3": ["GL"],
    "Zone 4": ["E", "EC", "N", "NW", "SE", "W", "WC"],
    "Zone 5": ["SW"],
    "Zone 6": ["DA", "HA", "IG", "RM", "TW", "WD"]
}

# Pallet Base Costs (Priority)
PALLET_RATES = {
    "Zone 2": {"Micro": 45.50, "Quarter": 50.00, "Half": 52.50, "Full": 60.00},
    "Zone 3": {"Micro": 46.50, "Quarter": 50.50, "Half": 53.50, "Full": 60.00},
    "Zone 4": {"Micro": 72.50, "Quarter": 75.50, "Half": 76.50, "Full": 79.50},
    "Zone 5": {"Micro": 72.50, "Quarter": 75.50, "Half": 76.50, "Full": 79.50},
    "Zone 6": {"Micro": 59.50, "Quarter": 62.00, "Half": 65.00, "Full": 70.00}
}

# Same Day Vehicle PPM (Price Per Mile)
VEHICLE_PPM = {
    "Van": 2.50,
    "Lorry": 3.50
}

# ==========================================
# 2. THE TABS & UI
# ==========================================

tab_pallet, tab_dhl, tab_van = st.tabs(["📦 UPN Pallets", "✉️ DHL Parcels", "🚐 Same Day Vehicle"])

# --- TAB 1: PALLET NETWORK ---
with tab_pallet:
    st.subheader("Automated Pallet Quote")
    
    col1, col2 = st.columns(2)
    with col1:
        st.write("**1. Destination & Service**")
        p_postcode = st.text_input("Postcode or area (e.g. B, CV, GL, or CV34 6TT)").upper().strip()
        p_qty = st.number_input("Quantity of Pallets", min_value=1, value=1)
        p_service = st.selectbox("Service Level", ["Priority", "Standard"])
        
    with col2:
        st.write("**2. Dimensions (mm)**")
        d1, d2, d3 = st.columns(3)
        p_len_mm = d1.number_input("Length (mm)", value=1200)
        p_wid_mm = d2.number_input("Width (mm)", value=1000)
        p_hei_mm = d3.number_input("Height (mm)", value=1000)
        
        p_weight = st.selectbox("Weight Bracket", [150, 300, 600, 1200], format_func=lambda x: f"Max {x} kg")
        p_markup = st.number_input("KEP Margin (%)", min_value=0, value=40, key="p_mark")

    if st.button("Generate Pallet Quote", use_container_width=True):
        if not p_postcode:
            st.warning("Please enter a postcode prefix.")
        else:
            # Accept a full postcode ("CV34 6TT") as well as a bare area
            # code ("CV"): take the leading letters only. Previously this
            # was an exact match against the prefix list, so anything with
            # a number in it fell through to the Zone 2 default.
            area = re.match(r"^[A-Z]+", p_postcode)
            area = area.group(0) if area else p_postcode

            detected_zone = next(
                (z for z, prefixes in PALLET_POSTCODES.items() if area in prefixes),
                None,
            )
            if detected_zone is None:
                safe_zone = "Zone 2"
                detected_zone = f"Zone 2 (assumed - '{area}' not in the zone map)"
                st.warning(
                    f"Postcode area **{area}** isn't in the zone map, so this quote assumes "
                    f"**Zone 2** rates. Check the real zone before sending it out - if it's "
                    f"actually a London/Home Counties zone, this quote is too low."
                )
            else:
                safe_zone = detected_zone
            
            p_len_m = p_len_mm / 1000
            p_wid_m = p_wid_mm / 1000
            p_hei_m = p_hei_mm / 1000
            
            spaces_len = math.ceil(p_len_m / 1.2)
            spaces_wid = math.ceil(p_wid_m / 1.2)
            billable_spaces_per_pallet = spaces_len * spaces_wid
            total_billable_spaces = billable_spaces_per_pallet * p_qty

            assigned_size = "Full"
            if p_weight <= 150 and p_hei_m <= 0.6: assigned_size = "Micro"
            elif p_weight <= 300 and p_hei_m <= 0.6: assigned_size = "Quarter"
            elif p_weight <= 600 and p_hei_m <= 2.2: assigned_size = "Half"
            elif p_weight <= 1200 and p_hei_m <= 2.2: assigned_size = "Full"

            base_rate = PALLET_RATES[safe_zone].get(assigned_size, 60.00)
            if p_service == "Standard":
                base_rate = max(0, base_rate - 4.00) 
            
            job_rate_internal = base_rate * total_billable_spaces
            sell_price = job_rate_internal * (1 + (p_markup / 100))

            st.markdown(f"""
            <div class='metric-card'>
                <h4>Total KEP Sell Price</h4>
                <p class='price-text'>£{sell_price:,.2f}</p>
            </div>
            """, unsafe_allow_html=True)

            with st.expander("🔍 View Working Out & Transparency"):
                st.markdown(f"""
                <div class='working-out-box'>
                <b>1. Data Parsing:</b><br>
                - Postcode '{p_postcode}' mapped to: <b>{detected_zone}</b><br>
                - Converted dimensions: <b>{p_len_m:.2f}m x {p_wid_m:.2f}m x {p_hei_m:.2f}m</b><br><br>
                <b>2. Routing & Logic:</b><br>
                - Footprint check: Takes up {billable_spaces_per_pallet} pallet space(s) each. Total Spaces: <b>{total_billable_spaces}</b><br>
                - Sizing matrix: Weight ({p_weight}kg) + Height ({p_hei_m}m) flags as a <b>{assigned_size}</b> pallet.<br><br>
                <b>3. Cost Breakdown:</b><br>
                - Base Rate ({safe_zone} / {assigned_size} / {p_service}): £{base_rate:.2f}<br>
                - Internal Cost (Rate x Spaces): £{job_rate_internal:.2f}<br>
                - Applied Margin: {p_markup}%<br>
                - Final Sell: <b>£{sell_price:.2f}</b>
                </div>
                """, unsafe_allow_html=True)


# --- TAB 2: DHL PARCELS ---
with tab_dhl:
    st.subheader("Automated DHL Quote")
    
    col1, col2 = st.columns(2)
    with col1:
        st.write("**1. Package Data**")
        d_qty = st.number_input("Number of Addresses/Boxes", min_value=1, value=1)
        d_weight = st.number_input("Weight per Box (kg)", min_value=0.1, value=2.0, step=0.5)
        
        d1, d2, d3 = st.columns(3)
        d_len_mm = d1.number_input("Length (mm) ", value=1000)
        d_wid_mm = d2.number_input("Width (mm) ", value=290)
        d_hei_mm = d3.number_input("Height (mm) ", value=100)

    with col2:
        st.write("**2. Service Options**")
        d_service = st.selectbox("Service Required", list(DHL_RATES.keys()))
        d_markup = st.number_input("KEP Custom Margin (%)", min_value=0, value=30, key="d_mark")

    if st.button("Generate DHL Quote Options", use_container_width=True):
        
        d_len_cm = d_len_mm / 10
        d_wid_cm = d_wid_mm / 10
        d_hei_cm = d_hei_mm / 10

        rates = DHL_RATES[d_service]
        per_box_cost = rates["base"]
        
        overweight_cost = 0
        if d_weight > 20:
            extra_kg = math.ceil(d_weight - 20)
            overweight_cost = extra_kg * rates["per_kg_over_20"]
            per_box_cost += overweight_cost
            
        ll_surcharge = 0
        max_dim_cm = max(d_len_cm, d_wid_cm, d_hei_cm)
        if max_dim_cm >= 140 and max_dim_cm < 160: ll_surcharge = 7.50
        elif max_dim_cm >= 160: ll_surcharge = 15.00
        
        per_box_cost += ll_surcharge
        internal_total = per_box_cost * d_qty
        
        # --- CALCULATE ALL 4 PRICING OPTIONS ---
        opt1_per_box = per_box_cost * (1 + (d_markup / 100))
        opt1_total = opt1_per_box * d_qty
        
        opt2_per_box = 9.95
        opt2_total = opt2_per_box * d_qty
        
        opt3_per_box = 10.95
        opt3_total = opt3_per_box * d_qty
        
        opt4_per_box = 12.95
        opt4_total = opt4_per_box * d_qty

        # Display the side-by-side pricing grid
        st.write(f"### Pricing Options (Internal Cost: £{internal_total:.2f} / £{per_box_cost:.2f} per box)")
        
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f"<div class='metric-card'><h4>Custom {d_markup}%</h4><p class='price-text'>£{opt1_total:,.2f}</p><p style='color:gray;'>£{opt1_per_box:,.2f} per box</p></div>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<div class='metric-card'><h4>Flat Tier 1</h4><p class='price-text'>£{opt2_total:,.2f}</p><p style='color:gray;'>£9.95 per box</p></div>", unsafe_allow_html=True)
        with c3:
            st.markdown(f"<div class='metric-card'><h4>Flat Tier 2</h4><p class='price-text'>£{opt3_total:,.2f}</p><p style='color:gray;'>£10.95 per box</p></div>", unsafe_allow_html=True)
        with c4:
            st.markdown(f"<div class='metric-card'><h4>Flat Tier 3</h4><p class='price-text'>£{opt4_total:,.2f}</p><p style='color:gray;'>£12.95 per box</p></div>", unsafe_allow_html=True)

        with st.expander("🔍 View Working Out & Transparency"):
            st.markdown(f"""
            <div class='working-out-box'>
            <b>1. Data Parsing:</b><br>
            - Converted dimensions: <b>{d_len_cm:.1f}cm x {d_wid_cm:.1f}cm x {d_hei_cm:.1f}cm</b><br>
            - Longest side is {max_dim_cm:.1f}cm.<br><br>
            <b>2. Routing & Surcharges:</b><br>
            - Overweight charge: Box is {d_weight}kg. ({overweight_cost > 0}) -> <b>£{overweight_cost:.2f}</b><br>
            - Long Length check: (>= 140cm is £7.50, >= 160cm is £15.00) -> <b>£{ll_surcharge:.2f}</b><br><br>
            <b>3. Cost Breakdown:</b><br>
            - Base {d_service} Rate: £{rates['base']:.2f}<br>
            - Internal Cost Per Box: £{per_box_cost:.2f}<br>
            - Total Internal Cost (x{d_qty} boxes): £{internal_total:.2f}
            </div>
            """, unsafe_allow_html=True)


# --- TAB 3: SAME DAY VAN ---
with tab_van:
    st.subheader("Dedicated Same Day Vehicle")
    
    col1, col2 = st.columns(2)
    with col1:
        st.write("**1. Route Data**")
        v_vehicle = st.selectbox("Vehicle Type", ["Van", "Lorry"])
        v_distance = st.number_input("Total Distance (Miles)", min_value=1, value=166)
    with col2:
        st.write("**2. Commercials**")
        v_markup = st.number_input("KEP Margin (%)", min_value=0, value=20, key="v_mark")
        
    if st.button("Generate Vehicle Quote", use_container_width=True):
        
        ppm = VEHICLE_PPM[v_vehicle]
        internal_total = v_distance * ppm
        sell_price = internal_total * (1 + (v_markup / 100))
        
        st.markdown(f"""
        <div class='metric-card'>
            <h4>Total KEP Sell Price</h4>
            <p class='price-text'>£{sell_price:,.2f}</p>
        </div>
        """, unsafe_allow_html=True)
        
        with st.expander("🔍 View Working Out & Transparency"):
            st.markdown(f"""
            <div class='working-out-box'>
            <b>1. Logic Check:</b><br>
            - Selected vehicle '{v_vehicle}' is mapped to a Price Per Mile of <b>£{ppm:.2f}</b><br><br>
            <b>2. Cost Breakdown:</b><br>
            - Distance Math: {v_distance} miles * £{ppm:.2f} = £{internal_total:.2f} internal cost.<br>
            - Applied Margin: {v_markup}%<br>
            - Final Sell: <b>£{sell_price:.2f}</b>
            </div>
            """, unsafe_allow_html=True)
