import streamlit as st
import pandas as pd
import os
import datetime

from utils import locked_save

st.set_page_config(page_title="Inventory Control", page_icon="📦", layout="wide")

# --- UI STYLING ---
st.markdown("""
    <style>
    .metric-card { background-color: #f8f9fa; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; text-align: center; }
    .stock-high { color: #27ae60; font-size: 28px; font-weight: bold; margin: 0; }
    .stock-low { color: #d9534f; font-size: 28px; font-weight: bold; margin: 0; }
    .stButton>button { background-color: #004B87; color: white; border-radius: 4px; font-weight: bold; padding: 10px; width: 100%; border: none; font-size: 16px; }
    .stButton>button:hover { background-color: #003666; color: white; }
    .success-banner { padding: 20px; background-color: #d1fae5; border: 2px solid #10b981; border-radius: 8px; color: #065f46; text-align: center; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

st.title("📦 Live Inventory & Goods-In Allocator")
st.write("Manage warehouse locations, track material specs, and allocate stock to KEP Jobs.")

# --- SESSION STATE INITIALIZATION ---
# This allows the app to "remember" that an action just happened even after the page reloads
if 'action_feedback' not in st.session_state:
    st.session_state.action_feedback = None

# --- VISUAL FEEDBACK BANNER ---
# If a button was clicked on the previous screen, display this massive banner now
if st.session_state.action_feedback:
    st.markdown(f"<div class='success-banner'><h2>{st.session_state.action_feedback}</h2></div>", unsafe_allow_html=True)
    st.toast(st.session_state.action_feedback, icon="✅")
    # Clear the message so it doesn't show up again on the next click
    st.session_state.action_feedback = None

st.divider()

# --- DATABASE MANAGEMENT ---
DB_FILE = "live_inventory.csv"

def load_inventory():
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
        # Backwards compatibility
        if 'Size' not in df.columns: df.insert(2, 'Size', '')
        if 'Thickness' not in df.columns: df.insert(3, 'Thickness', '')
    else:
        df = pd.DataFrame(columns=["SKU", "Description", "Size", "Thickness", "Location", "Quantity", "Last Updated"])
    
    df.fillna('', inplace=True)
    return df

def _write_inventory(df):
    df.to_csv(DB_FILE, index=False)


def save_inventory(df):
    # Wrapped in a file lock so two people booking stock in at the same
    # moment can't overwrite each other's row.
    locked_save(DB_FILE, _write_inventory, df)

# Load current data
inventory_df = load_inventory()

# --- THE APP INTERFACE ---
tab1, tab2, tab3 = st.tabs(["📥 Goods In (Receive Stock)", "📤 Allocate (Assign to Job)", "📊 Live Stock Board"])

# ==========================================
# TAB 1: GOODS IN (RECEIVE DELIVERY)
# ==========================================
with tab1:
    st.subheader("Log Incoming Delivery")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        in_sku = st.text_input("Item Code / SKU", placeholder="e.g. XLD20565")
        in_desc = st.text_input("Material Description", placeholder="e.g. Foamex, Silk, Uncoated")
    with col2:
        in_size = st.text_input("Sheet Size", placeholder="e.g. 1220x2440mm, B1, SRA3")
        in_thickness = st.text_input("Thickness / Weight", placeholder="e.g. 5mm, 150gsm, 400mic")
    with col3:
        in_qty = st.number_input("Quantity Received (Sheets/Units)", min_value=1, value=1000)
        locations = ["Bay A1 (Racking)", "Bay A2 (Racking)", "Bay B (Floor)", "Studio Holding", "Mezzanine", "Custom..."]
        in_loc = st.selectbox("Assign Warehouse Location", locations)
        if in_loc == "Custom...":
            in_loc = st.text_input("Type Custom Location")
            
    if st.button("📥 Book Stock into Warehouse"):
        if in_sku and in_desc:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            
            match = (
                (inventory_df['SKU'] == in_sku) & 
                (inventory_df['Location'] == in_loc) &
                (inventory_df['Size'] == in_size) &
                (inventory_df['Thickness'] == in_thickness)
            )
            
            if match.any():
                inventory_df.loc[match, 'Quantity'] += in_qty
                inventory_df.loc[match, 'Last Updated'] = now
                # Save the success message to memory instead of printing it instantly
                st.session_state.action_feedback = f"✅ SUCCESS: Added {in_qty} sheets to existing stock in {in_loc}."
            else:
                new_row = pd.DataFrame({
                    "SKU": [in_sku], "Description": [in_desc], 
                    "Size": [in_size], "Thickness": [in_thickness],
                    "Location": [in_loc], "Quantity": [in_qty], "Last Updated": [now]
                })
                inventory_df = pd.concat([inventory_df, new_row], ignore_index=True)
                st.session_state.action_feedback = f"✅ SUCCESS: Booked {in_qty} sheets of NEW stock into {in_loc}."
                
            save_inventory(inventory_df)
            st.rerun() # Reload the page to show the massive banner
        else:
            st.error("Please enter at least a SKU and Description.")

# ==========================================
# TAB 2: ALLOCATE (GOODS OUT TO JOB)
# ==========================================
with tab2:
    st.subheader("Allocate Stock to Job")
    
    if inventory_df.empty:
        st.info("Warehouse is currently empty. Book stock in via the 'Goods In' tab.")
    else:
        available_stock = inventory_df[inventory_df['Quantity'] > 0]
        
        col_out1, col_out2 = st.columns([2, 1])
        
        with col_out1:
            def build_display_string(row):
                spec_parts = []
                if row.get('Size'): spec_parts.append(str(row['Size']))
                if row.get('Thickness'): spec_parts.append(str(row['Thickness']))
                spec_str = f" ({', '.join(spec_parts)})" if spec_parts else ""
                return f"{row['SKU']} - {row['Description']}{spec_str} | Loc: {row['Location']} (Current: {row['Quantity']})"

            options = available_stock.apply(build_display_string, axis=1).tolist()
            selected_item = st.selectbox("Select Material to Allocate:", options)
        
        with col_out2:
            job_no = st.text_input("KEP Job Number", placeholder="e.g. 353319")
            
        if selected_item:
            selected_idx = options.index(selected_item)
            selected_row = available_stock.iloc[selected_idx]
            max_qty = int(selected_row['Quantity'])
            
            out_qty = st.number_input(f"Quantity to Remove (Max: {max_qty})", min_value=1, max_value=max_qty, value=1)
            
            if st.button("📤 Allocate to Job"):
                if job_no:
                    real_index = selected_row.name
                    inventory_df.at[real_index, 'Quantity'] -= out_qty
                    inventory_df.at[real_index, 'Last Updated'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                    
                    save_inventory(inventory_df)
                    
                    # Save the success message to memory
                    st.session_state.action_feedback = f"✅ SUCCESS: Allocated {out_qty} sheets to KEP Job {job_no}."
                    st.rerun() # Reload the page to show the massive banner
                else:
                    st.error("You must enter a Job Number to track where this material went.")

# ==========================================
# TAB 3: LIVE STOCK BOARD
# ==========================================
with tab3:
    st.subheader("📊 Live Warehouse Status")
    
    if inventory_df.empty:
        st.write("No stock data available.")
    else:
        total_items = len(inventory_df[inventory_df['Quantity'] > 0])
        total_sheets = inventory_df['Quantity'].sum()
        
        m1, m2 = st.columns(2)
        with m1:
            st.markdown(f"<div class='metric-card'><h4>Active Pallets/Locations</h4><p class='stock-high'>{total_items}</p></div>", unsafe_allow_html=True)
        with m2:
            st.markdown(f"<div class='metric-card'><h4>Total Sheets in Warehouse</h4><p class='stock-high'>{total_sheets:,}</p></div>", unsafe_allow_html=True)
            
        st.divider()
        
        search = st.text_input("🔍 Search Inventory (by SKU, Description, Size, GSM, or Bay)")
        
        display_df = inventory_df[inventory_df['Quantity'] > 0].sort_values(by="Location")
        
        if search:
            display_df = display_df[
                display_df.apply(lambda row: row.astype(str).str.contains(search, case=False).any(), axis=1)
            ]
            
        st.dataframe(display_df, use_container_width=True, hide_index=True)
