import streamlit as st
import pandas as pd
import os
import datetime
import calendar

from storage import (ensure_share_token, init_db, list_campaigns,
                     revoke_share_token, upsert_campaign)
from utils import locked_save

st.set_page_config(page_title="Campaign Schedule", page_icon="📅", layout="wide")

# --- UI STYLING ---
st.markdown("""
    <style>
    .metric-card { background-color: #f8f9fa; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; text-align: center; }
    .stButton>button { background-color: #004B87; color: white; border-radius: 4px; font-weight: bold; padding: 10px; width: 100%; border: none; }
    .stButton>button:hover { background-color: #003666; color: white; }
    
    /* --- MOBILE RESPONSIVE WRAPPER --- */
    .table-wrapper {
        width: 100%;
        overflow-x: auto;
        -webkit-overflow-scrolling: touch; /* Enables smooth swiping on iPhone */
        margin-bottom: 20px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    /* Global Calendar Styling (Added min-width to stop mobile squishing) */
    .cal-container { width: 100%; min-width: 800px; border-collapse: collapse; table-layout: fixed; margin-top: 0px; font-family: Arial, sans-serif; }
    .cal-header { background-color: #f8f9fa; text-align: center; padding: 10px; font-weight: bold; border: 1px solid #ddd; color: #555; position: sticky; top: 0; z-index: 1; }
    .cal-cell { border: 1px solid #ddd; vertical-align: top; height: 120px; padding: 5px; background-color: #fff; }
    .cal-cell-empty { background-color: #f9f9f9; border: 1px solid #eee; }
    
    /* Standard Date Header for Tab 1 */
    .date-standard { background-color: #f1f5f9; color: #334155; font-weight: bold; font-size: 14px; padding: 4px; border-radius: 4px; margin-bottom: 5px; }
    
    /* Capacity Headers for Tab 3 */
    .cap-safe { background-color: #d1fae5; color: #065f46; font-weight: bold; font-size: 14px; padding: 4px; border-radius: 4px; margin-bottom: 5px; display: flex; justify-content: space-between;} 
    .cap-warn { background-color: #fef08a; color: #854d0e; font-weight: bold; font-size: 14px; padding: 4px; border-radius: 4px; margin-bottom: 5px; display: flex; justify-content: space-between;} 
    .cap-clash { background-color: #fee2e2; color: #991b1b; border: 1px solid #ef4444; font-weight: bold; font-size: 14px; padding: 4px; border-radius: 4px; margin-bottom: 5px; display: flex; justify-content: space-between;} 
    
    /* Job Badges (Shared) */
    .job-badge { font-size: 11px; padding: 4px; margin-bottom: 4px; border-radius: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; line-height: 1.2; }
    
    /* Specific Status Colors for Tab 1 */
    .badge-artwork { background-color: #fee2e2; border-left: 3px solid #ef4444; color: #991b1b; }
    .badge-prod { background-color: #ffedd5; border-left: 3px solid #f97316; color: #c2410c; }
    .badge-collate { background-color: #fef08a; border-left: 3px solid #eab308; color: #854d0e; }
    .badge-dispatch { background-color: #d1fae5; border-left: 3px solid #22c55e; color: #065f46; }
    
    /* Default Blue Badge for Tab 3 */
    .badge-default { background-color: #e0f2fe; border-left: 3px solid #0284c7; color: #0369a1; }
    
    </style>
    """, unsafe_allow_html=True)

st.title("📅 Master Campaign Schedule")
st.write("Live dispatch tracker, interactive capacity calendar, and file vault.")

# --- DATABASE MANAGEMENT ---
init_db()

DB_FILE = "campaign_database.csv"
UPLOAD_DIR = "campaign_files"
MAX_DAILY_HOURS = 16.0 

if not os.path.exists(UPLOAD_DIR): os.makedirs(UPLOAD_DIR)

def load_db():
    if os.path.exists(DB_FILE): df = pd.read_csv(DB_FILE)
    else: df = pd.DataFrame(columns=["ID", "Client", "Campaign Name", "AM", "Dispatch Date", "Stores (Qty)", "Collation (Hrs)", "Status", "Notes"])
    df['Dispatch Date'] = pd.to_datetime(df['Dispatch Date'], errors='coerce')
    return df

def _write_db(df):
    df = df.copy()
    # Coerce first: if this column arrives as plain dates/strings the bare
    # .dt accessor raises and the save silently fails.
    df['Dispatch Date'] = pd.to_datetime(df['Dispatch Date'], errors='coerce')
    df['Dispatch Date'] = df['Dispatch Date'].dt.strftime('%Y-%m-%d')
    df.to_csv(DB_FILE, index=False)


def save_db(df):
    locked_save(DB_FILE, _write_db, df)

df = load_db()

# --- APP TABS ---
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📋 Live Status Calendar", 
    "➕ Add Campaign", 
    "🗓️ Visual Capacity Calendar", 
    "📁 File Vault",
    "⚙️ Import Legacy Data",
    "🔗 Client Links"
])

# ==========================================
# TAB 1: LIVE STATUS CALENDAR + EDITOR
# ==========================================
with tab1:
    st.subheader("Live Status Calendar")
    st.write("A visual overview of dispatch dates. Campaigns are colour-coded by their current production status.")
    
    if df.empty:
        st.info("No campaigns active. Go to 'Add Campaign' or 'Import Legacy Data' to start.")
    else:
        # --- THE STATUS CALENDAR ---
        col_m1, col_y1, _ = st.columns([1, 1, 3])
        current_year = datetime.datetime.now().year
        with col_m1: selected_month_t1 = st.selectbox("Month", range(1, 13), index=datetime.datetime.now().month - 1, format_func=lambda x: calendar.month_name[x], key="t1_month")
        with col_y1: selected_year_t1 = st.selectbox("Year", range(current_year - 1, current_year + 3), index=1, key="t1_year")
            
        df['Date_Str_T1'] = df['Dispatch Date'].dt.strftime('%Y-%m-%d')
        cal_t1 = calendar.monthcalendar(selected_year_t1, selected_month_t1)
        
        # Wrapped the table in the new mobile-responsive div
        html_t1 = "<div class='table-wrapper'><table class='cal-container'>"
        html_t1 += "<tr><th class='cal-header'>Mon</th><th class='cal-header'>Tue</th><th class='cal-header'>Wed</th><th class='cal-header'>Thu</th><th class='cal-header'>Fri</th><th class='cal-header'>Sat</th><th class='cal-header'>Sun</th></tr>"
        
        for week in cal_t1:
            html_t1 += "<tr>"
            for day in week:
                if day == 0: html_t1 += "<td class='cal-cell-empty'></td>"
                else:
                    date_str = f"{selected_year_t1}-{selected_month_t1:02d}-{day:02d}"
                    day_jobs = df[df['Date_Str_T1'] == date_str]
                    
                    html_t1 += f"<td class='cal-cell'><div class='date-standard'>{day}</div>"
                    
                    for _, job in day_jobs.iterrows():
                        # Determine colour based on Status
                        status = str(job['Status'])
                        if "Artwork" in status: b_class = "badge-artwork"
                        elif "Production" in status: b_class = "badge-prod"
                        elif "Picking" in status: b_class = "badge-collate"
                        else: b_class = "badge-dispatch"
                        
                        html_t1 += f"<div class='job-badge {b_class}' title='{job['Campaign Name']}'><b>{job['Client']}</b><br>{job['Campaign Name']}</div>"
                    html_t1 += "</td>"
            html_t1 += "</tr>"
        html_t1 += "</table></div>" # Closed the wrapper here
        st.markdown(html_t1, unsafe_allow_html=True)
        
        st.divider()
        
        # --- THE DATA EDITOR ---
        st.subheader("Edit Master Data")
        st.write("Double-click any cell below to change dates or update the status. The calendar above will update instantly.")
        
        display_df = df.sort_values(by="Dispatch Date", ascending=True).reset_index(drop=True)
        display_df['Dispatch Date'] = display_df['Dispatch Date'].dt.date
        
        edited_df = st.data_editor(
            display_df,
            column_config={
                "ID": st.column_config.TextColumn("ID", disabled=True),
                "Dispatch Date": st.column_config.DateColumn("Dispatch Date", format="DD/MM/YYYY", required=True),
                "Status": st.column_config.SelectboxColumn("Status", options=["🔴 Awaiting Artwork", "🟠 In Production", "🟡 Picking/Collation", "🟢 Dispatched"], required=True),
                "Collation (Hrs)": st.column_config.NumberColumn("Collation (Hrs)", min_value=0, format="%d"),
                "Stores (Qty)": st.column_config.NumberColumn("Stores (Qty)", min_value=0, format="%d"),
                "Date_Str_T1": None # Hide the helper column
            },
            use_container_width=True, hide_index=True, num_rows="dynamic"
        )
        
        if st.button("💾 Save Board Changes"):
            edited_df['Dispatch Date'] = pd.to_datetime(edited_df['Dispatch Date'])
            # Remove helper column before saving
            if 'Date_Str_T1' in edited_df.columns:
                edited_df = edited_df.drop(columns=['Date_Str_T1'])
            save_db(edited_df)
            st.success("✅ Master Schedule Updated!")
            st.rerun()

# ==========================================
# TAB 2: ADD NEW CAMPAIGN
# ==========================================
with tab2:
    st.subheader("Log a New Campaign")
    st.markdown("<div style='background-color: #f8f9fa; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0;'>", unsafe_allow_html=True)
    with st.form("new_campaign_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            client = st.text_input("Client", placeholder="e.g. Greggs")
            campaign = st.text_input("Campaign Name", placeholder="e.g. Week 40")
            am = st.text_input("Account Manager", placeholder="e.g. MS")
        with col2:
            dispatch_date = st.date_input("Target Dispatch Date")
            stores = st.number_input("Amount of Stores", min_value=1, value=100)
        with col3:
            collation_hrs = st.number_input("Est. Collation (Hours)", min_value=0.0, value=4.0, step=0.5)
            status = st.selectbox("Initial Status", ["🔴 Awaiting Artwork", "🟠 In Production", "🟡 Picking/Collation", "🟢 Dispatched"])
        notes = st.text_area("Notes")
        
        if st.form_submit_button("➕ Add to Master Schedule"):
            if client and campaign:
                new_id = f"{client[:3].upper()}-{datetime.datetime.now().strftime('%m%d%H%M')}"
                new_row = pd.DataFrame([{"ID": new_id, "Client": client, "Campaign Name": campaign, "AM": am, "Dispatch Date": pd.to_datetime(dispatch_date), "Stores (Qty)": stores, "Collation (Hrs)": collation_hrs, "Status": status, "Notes": notes}])
                # Drop helper col if it exists
                if 'Date_Str_T1' in df.columns: df = df.drop(columns=['Date_Str_T1'])
                df = pd.concat([df, new_row], ignore_index=True)
                save_db(df)
                st.success(f"✅ Added {campaign}")
                st.rerun()
            else:
                st.error("Client and Campaign required.")
    st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# TAB 3: VISUAL CAPACITY CALENDAR
# ==========================================
with tab3:
    st.subheader("🗓️ Production Capacity Calendar")
    st.write(f"Visually maps daily dispatch load. Days exceeding the **{MAX_DAILY_HOURS}-hour capacity limit** will turn red.")
    
    active_df = df[df["Status"] != "🟢 Dispatched"].copy()
    
    if active_df.empty:
        st.info("No active campaigns to display.")
    else:
        col_m3, col_y3, _ = st.columns([1, 1, 3])
        with col_m3: selected_month_t3 = st.selectbox("Month", range(1, 13), index=datetime.datetime.now().month - 1, format_func=lambda x: calendar.month_name[x], key="t3_month")
        with col_y3: selected_year_t3 = st.selectbox("Year", range(datetime.datetime.now().year - 1, datetime.datetime.now().year + 3), index=1, key="t3_year")
            
        active_df['Date_Str'] = active_df['Dispatch Date'].dt.strftime('%Y-%m-%d')
        cal_t3 = calendar.monthcalendar(selected_year_t3, selected_month_t3)
        
        # Wrapped the capacity table for mobile swiping too
        html_t3 = "<div class='table-wrapper'><table class='cal-container'>"
        html_t3 += "<tr><th class='cal-header'>Mon</th><th class='cal-header'>Tue</th><th class='cal-header'>Wed</th><th class='cal-header'>Thu</th><th class='cal-header'>Fri</th><th class='cal-header'>Sat</th><th class='cal-header'>Sun</th></tr>"
        
        for week in cal_t3:
            html_t3 += "<tr>"
            for day in week:
                if day == 0: html_t3 += "<td class='cal-cell-empty'></td>"
                else:
                    date_str = f"{selected_year_t3}-{selected_month_t3:02d}-{day:02d}"
                    day_jobs = active_df[active_df['Date_Str'] == date_str]
                    total_hours = day_jobs['Collation (Hrs)'].sum()
                    
                    if total_hours == 0: header_class, hours_text = "cap-safe", ""
                    elif total_hours <= MAX_DAILY_HOURS * 0.8: header_class, hours_text = "cap-safe", f"{total_hours}h"
                    elif total_hours <= MAX_DAILY_HOURS: header_class, hours_text = "cap-warn", f"{total_hours}h"
                    else: header_class, hours_text = "cap-clash", f"🚨 {total_hours}h"
                    
                    html_t3 += f"<td class='cal-cell'><div class='{header_class}'><span>{day}</span><span>{hours_text}</span></div>"
                    for _, job in day_jobs.iterrows(): html_t3 += f"<div class='job-badge badge-default' title='{job['Campaign Name']}'><b>{job['Client']}</b><br>{job['Campaign Name']}</div>"
                    html_t3 += "</td>"
            html_t3 += "</tr>"
        html_t3 += "</table></div>" # Closed the wrapper here
        st.markdown(html_t3, unsafe_allow_html=True)

# ==========================================
# TAB 4: FILE VAULT
# ==========================================
with tab4:
    st.subheader("📁 Campaign File Vault")
    if df.empty:
        st.info("Add a campaign first.")
    else:
        col_v1, col_v2 = st.columns(2)
        with col_v1:
            campaign_list = df['ID'] + " | " + df['Client'] + " - " + df['Campaign Name']
            selected_camp = st.selectbox("Attach file to:", campaign_list)
            uploaded_file = st.file_uploader("Upload Matrix/Pick List", type=["pdf", "csv", "xlsx"])
            if st.button("📤 Upload") and uploaded_file:
                camp_id = selected_camp.split(" | ")[0]
                with open(os.path.join(UPLOAD_DIR, f"{camp_id}_{uploaded_file.name}"), "wb") as f: f.write(uploaded_file.getbuffer())
                st.success("✅ File saved.")
        with col_v2:
            st.write("**Retrieve Files**")
            files = os.listdir(UPLOAD_DIR)
            if not files: st.info("Vault is empty.")
            else:
                for f_name in sorted(files):
                    with open(os.path.join(UPLOAD_DIR, f_name), "rb") as file:
                        st.download_button(label=f"⬇️ {f_name}", data=file, file_name=f_name)

# ==========================================
# TAB 5: IMPORT LEGACY DATA
# ==========================================
with tab5:
    st.subheader("⚙️ Import Legacy Excel Data")
    import_file = st.file_uploader("Upload 'KEP Campaign Overview'", type=["csv", "xlsx"])
    if import_file:
        try:
            if import_file.name.endswith('.csv'): raw_df = pd.read_csv(import_file).dropna(how='all', axis=0).dropna(how='all', axis=1)
            else: raw_df = pd.read_excel(import_file).dropna(how='all', axis=0).dropna(how='all', axis=1)
            
            st.dataframe(raw_df.head(3))
            col_opts = ["--- Ignore ---"] + list(raw_df.columns)
            
            m1, m2 = st.columns(2)
            with m1:
                map_client = st.selectbox("Client Name Column", col_opts)
                map_campaign = st.selectbox("Campaign Name Column", col_opts)
            with m2:
                map_date = st.selectbox("Dispatch Date Column", col_opts)
                
            if st.button("🔄 Import Data"):
                new_recs = []
                for _, row in raw_df.iterrows():
                    if map_client != "--- Ignore ---" and map_campaign != "--- Ignore ---":
                        c_val, camp_val = str(row[map_client]), str(row[map_campaign])
                        if c_val.lower() == 'nan' or not c_val.strip(): continue
                        
                        d_val = pd.NaT
                        if map_date != "--- Ignore ---":
                            try: d_val = pd.to_datetime(row[map_date])
                            except: pass
                            
                        new_recs.append({"ID": f"{c_val[:3].upper()}-IMP{datetime.datetime.now().strftime('%M%S%f')}", "Client": c_val, "Campaign Name": camp_val, "AM": "", "Dispatch Date": d_val, "Stores (Qty)": 0, "Collation (Hrs)": 4.0, "Status": "🔴 Awaiting Artwork", "Notes": "Imported"})
                
                if new_recs:
                    if 'Date_Str_T1' in df.columns: df = df.drop(columns=['Date_Str_T1'])
                    df = pd.concat([df, pd.DataFrame(new_recs)], ignore_index=True)
                    save_db(df)
                    st.success(f"✅ Imported {len(new_recs)} campaigns!")
                    st.rerun()
        except Exception as e: st.error(f"Error: {e}")

# ==========================================
# TAB 6: CLIENT LINKS
# ==========================================
with tab6:
    st.subheader("🔗 Client tracking links")
    st.write(
        "Give a client a link they can refresh themselves instead of emailing "
        "them a dashboard. The link shows delivery status for that campaign only."
    )

    if not st.secrets.get("app_password"):
        st.warning(
            "**Turn the portal password on before sharing any link.** A share link "
            "only opens the client view — but without a password, anyone who removes "
            "the `?share=` part of the URL reaches the full internal portal. "
            "See README.md → *There's no access control by default*.",
            icon="⚠️",
        )

    base_url = st.text_input(
        "Portal address",
        value=st.session_state.get("kep_base_url", ""),
        placeholder="https://kep-portal.streamlit.app",
        key="kep_base_url",
        help="The address CSRs use to reach this portal. Used to build the shareable link.",
    )

    if df.empty:
        st.info("Add a campaign first.")
    else:
        # The calendar keeps campaigns in CSV; the share links need them in
        # the database. This copies them across (and is safe to re-run).
        if st.button("🔄 Sync campaigns to database"):
            synced = 0
            for _, row in df.iterrows():
                d = row.get("Dispatch Date")
                upsert_campaign(
                    campaign_id=str(row.get("ID", "")).strip(),
                    client=str(row.get("Client", "")).strip(),
                    name=str(row.get("Campaign Name", "")).strip(),
                    am=str(row.get("AM", "") or ""),
                    dispatch_date=(d.date().isoformat() if pd.notna(d) else None),
                    stores=int(pd.to_numeric(row.get("Stores (Qty)"), errors="coerce") or 0),
                    collation_hrs=float(pd.to_numeric(row.get("Collation (Hrs)"), errors="coerce") or 0),
                    status=str(row.get("Status", "") or ""),
                    notes=str(row.get("Notes", "") or ""),
                )
                synced += 1
            st.success(f"✅ Synced {synced} campaigns. You can now issue links for them.")

        stored = list_campaigns()
        if not stored:
            st.info("Nothing synced yet — press **Sync campaigns to database** above.")
        else:
            labels = {f"{c['client']} — {c['name']} ({c['id']})": c for c in stored}
            picked = st.selectbox("Campaign", list(labels.keys()))
            campaign = labels[picked]

            col_a, col_b = st.columns([3, 1])
            with col_a:
                if campaign.get("share_token"):
                    link = (
                        f"{base_url.rstrip('/')}/?share={campaign['share_token']}"
                        if base_url else f"?share={campaign['share_token']}"
                    )
                    st.text_input("Shareable link", value=link, key=f"link_{campaign['id']}")
                    if not base_url:
                        st.caption("Enter the portal address above to get the full link.")
                else:
                    st.caption("No link issued for this campaign yet.")

            with col_b:
                st.write("")
                if campaign.get("share_token"):
                    if st.button("Revoke", use_container_width=True):
                        revoke_share_token(campaign["id"])
                        st.success("Link revoked.")
                        st.rerun()
                else:
                    if st.button("Create link", use_container_width=True):
                        ensure_share_token(campaign["id"])
                        st.rerun()

            st.divider()
            st.write("**Links currently active**")
            active = [c for c in stored if c.get("share_token")]
            if not active:
                st.caption("None. Links you create will be listed here so you can see what's live.")
            else:
                st.dataframe(
                    [{"Campaign": f"{c['client']} — {c['name']}",
                      "Dispatch": c.get("dispatch_date") or "—",
                      "Status": c.get("status") or "—"} for c in active],
                    use_container_width=True, hide_index=True,
                )
                st.caption(
                    "Revoke links once a campaign is closed — a share link is a bearer "
                    "token, so anyone who has it can keep viewing that campaign."
                )
