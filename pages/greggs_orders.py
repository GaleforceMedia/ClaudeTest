import streamlit as st
import pandas as pd
import os
import datetime
import calendar

from utils import locked_save

st.set_page_config(page_title="Greggs Orders", page_icon="🥐", layout="wide")

# --- UI STYLING ---
st.markdown("""
    <style>
    .stButton>button { background-color: #004B87; color: white; border-radius: 4px; padding: 10px; width: 100%; border: none; font-weight: bold; }
    .stButton>button:hover { background-color: #003666; color: white; }
    
    /* --- MOBILE RESPONSIVE WRAPPER --- */
    .table-wrapper {
        width: 100%;
        overflow-x: auto;
        -webkit-overflow-scrolling: touch; 
        margin-bottom: 20px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    /* Global Calendar Styling */
    .cal-container { width: 100%; min-width: 800px; border-collapse: collapse; table-layout: fixed; margin-top: 10px; font-family: Arial, sans-serif; }
    .cal-header { background-color: #f8f9fa; text-align: center; padding: 10px; font-weight: bold; border: 1px solid #ddd; color: #004B87; }
    .cal-cell { border: 1px solid #ddd; vertical-align: top; height: 120px; padding: 5px; background-color: #fff; }
    .cal-cell-empty { background-color: #f9f9f9; border: 1px solid #eee; }
    
    /* Standard Date Header */
    .date-standard { background-color: #f1f5f9; color: #334155; font-weight: bold; font-size: 14px; padding: 4px; border-radius: 4px; margin-bottom: 5px; }
    
    /* Job Badges */
    .job-badge { font-size: 12px; font-weight: bold; padding: 4px; margin-bottom: 4px; border-radius: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; line-height: 1.2; }
    
    /* Specific Status Colors */
    .badge-pending { background-color: #fee2e2; border-left: 4px solid #ef4444; color: #991b1b; }
    .badge-picking { background-color: #fef08a; border-left: 4px solid #eab308; color: #854d0e; }
    .badge-dispatch { background-color: #d1fae5; border-left: 4px solid #22c55e; color: #065f46; }
    </style>
    """, unsafe_allow_html=True)

st.title("🥐 Greggs Store Orders")
st.write("Live dispatch tracker for ad-hoc Greggs store requests and replacement kits.")

# --- DATABASE MANAGEMENT ---
DB_FILE = "greggs_orders_db.csv"

def load_db():
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
        df['Dispatch Date'] = pd.to_datetime(df['Dispatch Date'], errors='coerce')
        
        # --- AUTO-DISPATCH LOGIC ---
        today = pd.Timestamp(datetime.date.today())
        mask = (df['Dispatch Date'] < today) & (df['Status'] != '🟢 Dispatched')
        df.loc[mask, 'Status'] = '🟢 Dispatched'
        return df
    return pd.DataFrame(columns=["Order ID", "Store Number", "Requested By", "Dispatch Date", "Order Details", "Status"])

def _write_db(df):
    # Force the column to be a datetime object to prevent the .dt accessor error
    df = df.copy()
    df['Dispatch Date'] = pd.to_datetime(df['Dispatch Date'], errors='coerce')
    # Now it is safe to format it for the CSV
    df['Dispatch Date'] = df['Dispatch Date'].dt.strftime('%Y-%m-%d')
    df.to_csv(DB_FILE, index=False)


def save_db(df):
    locked_save(DB_FILE, _write_db, df)

df = load_db()

# Split into Active/Dispatched
active_df = df[df['Status'] != '🟢 Dispatched'].copy()
dispatched_df = df[df['Status'] == '🟢 Dispatched'].copy()

# --- APP TABS ---
tab1, tab2, tab3 = st.tabs(["📋 Live Dispatch Calendar", "➕ Log Store Orders", "📦 Dispatched Archive"])

# ==========================================
# TAB 1: LIVE STATUS CALENDAR + EDITOR
# ==========================================
with tab1:
    st.subheader("Live Status Calendar")
    
    if active_df.empty:
        st.info("No active store orders. Go to 'Log Store Orders' to add requests.")
    else:
        col_m1, col_y1, _ = st.columns([1, 1, 3])
        current_year = datetime.datetime.now().year
        with col_m1: selected_month = st.selectbox("Month", range(1, 13), index=datetime.datetime.now().month - 1, format_func=lambda x: calendar.month_name[x])
        with col_y1: selected_year = st.selectbox("Year", range(current_year - 1, current_year + 2), index=1)
            
        active_df['Date_Str'] = active_df['Dispatch Date'].dt.strftime('%Y-%m-%d')
        cal_t1 = calendar.monthcalendar(selected_year, selected_month)
        
        # Mobile responsive wrapper
        html_t1 = "<div class='table-wrapper'><table class='cal-container'>"
        html_t1 += "<tr><th class='cal-header'>Mon</th><th class='cal-header'>Tue</th><th class='cal-header'>Wed</th><th class='cal-header'>Thu</th><th class='cal-header'>Fri</th><th class='cal-header'>Sat</th><th class='cal-header'>Sun</th></tr>"
        
        for week in cal_t1:
            html_t1 += "<tr>"
            for day in week:
                if day == 0: html_t1 += "<td class='cal-cell-empty'></td>"
                else:
                    date_str = f"{selected_year}-{selected_month:02d}-{day:02d}"
                    day_jobs = active_df[active_df['Date_Str'] == date_str]
                    
                    html_t1 += f"<td class='cal-cell'><div class='date-standard'>{day}</div>"
                    
                    for _, job in day_jobs.iterrows():
                        status = str(job['Status'])
                        if "Pending" in status: b_class = "badge-pending"
                        elif "Picking" in status: b_class = "badge-picking"
                        else: b_class = "badge-dispatch"
                        
                        # Formatting the Store Number to ensure it stands out
                        store_num = job['Store Number'] if str(job['Store Number']).upper().startswith('S') else f"S{job['Store Number']}"
                        
                        html_t1 += f"<div class='job-badge {b_class}' title='{job['Order Details']}'>{store_num}</div>"
                    html_t1 += "</td>"
            html_t1 += "</tr>"
        html_t1 += "</table></div>"
        st.markdown(html_t1, unsafe_allow_html=True)
        
        st.divider()
        
        st.subheader("Edit Master Data")
        st.write("Update status (e.g. to 'Picking/Packing') or change dates. Calendar updates instantly on save.")
        
        search = st.text_input("🔍 Search Active Orders (Store Number, Details...)")
        
        search_df = active_df.copy()
        if search:
            search_df = search_df[search_df.apply(lambda row: row.astype(str).str.contains(search, case=False).any(), axis=1)]
        
        # Format date for editor
        search_df['Dispatch Date'] = search_df['Dispatch Date'].dt.date
        
        edited_df = st.data_editor(
            search_df.sort_values("Dispatch Date"),
            column_config={
                "Order ID": st.column_config.TextColumn(disabled=True),
                "Dispatch Date": st.column_config.DateColumn(format="DD/MM/YYYY", required=True),
                "Status": st.column_config.SelectboxColumn(options=["🔴 Pending", "🟡 Picking/Packing", "🟢 Dispatched"], required=True),
                "Date_Str": None
            },
            use_container_width=True, hide_index=True, num_rows="dynamic"
        )
        
        if st.button("💾 Save Board Changes"):
            edited_df['Dispatch Date'] = pd.to_datetime(edited_df['Dispatch Date'])
            if 'Date_Str' in edited_df.columns: edited_df = edited_df.drop(columns=['Date_Str'])
            
            # Merge updates back to main dataframe
            updated_active = active_df.copy()
            updated_active.update(edited_df)
            
            # Save
            new_df = pd.concat([updated_active, dispatched_df], ignore_index=True)
            save_db(new_df)
            st.success("✅ Order Schedule Updated!")
            st.rerun()

# ==========================================
# TAB 2: ADD STORE ORDERS
# ==========================================
with tab2:
    st.subheader("Log Store Orders")
    
    col_single, col_bulk = st.columns(2, gap="large")
    
    with col_single:
        st.markdown("**Add a Single Store**")
        with st.form("add_single_store", clear_on_submit=True):
            store_no = st.text_input("Store Number", placeholder="e.g. S0123")
            requester = st.text_input("Requested By (AM)")
            details = st.text_input("Order Details/Kits Required", placeholder="e.g. Breakfast POS Kit")
            d_date = st.date_input("Target Dispatch Date")
            
            if st.form_submit_button("➕ Add Order"):
                if store_no:
                    new_id = f"GRG-{datetime.datetime.now().strftime('%M%S%f')}"
                    s_fmt = store_no if str(store_no).upper().startswith('S') else f"S{store_no}"
                    
                    new_row = pd.DataFrame([{"Order ID": new_id, "Store Number": s_fmt.upper(), "Requested By": requester, "Dispatch Date": pd.to_datetime(d_date), "Order Details": details, "Status": "🔴 Pending"}])
                    save_db(pd.concat([df, new_row], ignore_index=True))
                    st.success(f"✅ Added Store {s_fmt.upper()}")
                    st.rerun()
                else:
                    st.error("Store Number is required.")
                    
    with col_bulk:
        st.markdown("**Bulk Paste Stores**")
        st.write("Got a list from an email? Paste them here to log them all at once.")
        with st.form("add_bulk_store", clear_on_submit=True):
            store_list = st.text_area("Paste Store Numbers (one per line)", placeholder="S0123\nS0456\nS0789")
            bulk_requester = st.text_input("Requested By (AM) [Applies to all]")
            bulk_details = st.text_input("Order Details [Applies to all]", placeholder="e.g. Missing Ticket Replacements")
            bulk_date = st.date_input("Target Dispatch Date [Applies to all]")
            
            if st.form_submit_button("🚀 Bulk Add Orders"):
                if store_list.strip():
                    stores = [s.strip() for s in store_list.split('\n') if s.strip()]
                    new_records = []
                    
                    for i, s in enumerate(stores):
                        s_fmt = s if str(s).upper().startswith('S') else f"S{s}"
                        new_id = f"GRG-{datetime.datetime.now().strftime('%M%S')}-{i}"
                        new_records.append({"Order ID": new_id, "Store Number": s_fmt.upper(), "Requested By": bulk_requester, "Dispatch Date": pd.to_datetime(bulk_date), "Order Details": bulk_details, "Status": "🔴 Pending"})
                    
                    if new_records:
                        save_db(pd.concat([df, pd.DataFrame(new_records)], ignore_index=True))
                        st.success(f"✅ Successfully booked {len(new_records)} stores for dispatch!")
                        st.rerun()
                else:
                    st.error("Please paste at least one store number.")

# ==========================================
# TAB 3: ARCHIVE
# ==========================================
with tab3:
    st.subheader("📦 Dispatched Archive")
    st.write("Orders are automatically moved here once their dispatch date has passed.")
    
    search_arch = st.text_input("🔍 Search Archive (Store Number)")
    
    if search_arch:
        dispatched_df = dispatched_df[dispatched_df.apply(lambda row: row.astype(str).str.contains(search_arch, case=False).any(), axis=1)]
        
    st.dataframe(dispatched_df.sort_values("Dispatch Date", ascending=False), use_container_width=True, hide_index=True)
