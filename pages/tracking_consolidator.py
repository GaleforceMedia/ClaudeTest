import streamlit as st
import pandas as pd
import io
import zipfile
import datetime
import streamlit.components.v1 as components
from html import escape

from storage import init_db, list_campaigns, record_shipments
from utils import BRANDING, DEFAULT_BRAND, get_base64_image

st.set_page_config(page_title="Tracking Consolidator", page_icon="🚚", layout="wide")

init_db()

# --- UI STYLING ---
st.markdown("""
    <style>
    .stButton>button { background-color: #000000; color: white; border-radius: 4px; font-weight: bold; padding: 10px; width: 100%; border: none; }
    .stButton>button:hover { background-color: #333333; color: white; }
    h1, h2, h3 { font-family: 'Arial', sans-serif; }
    </style>
    """, unsafe_allow_html=True)

st.title("🚚 Post-Ship Tracking Consolidator")
st.write("Upload your DHL Dashboard Summary export. The system will separate the data by Account Number and generate branded HTML tracking dashboards & CSVs.")
st.divider()

# --- HELPER: HTML GENERATOR ---
def generate_branded_html(df, brand_code, date_str):
    brand = BRANDING.get(brand_code, DEFAULT_BRAND)
    
    # Check for logo
    logo_base64 = get_base64_image(brand.get('logo_file', '')) if brand.get('logo_file') else None
    
    # Build Header Logo HTML
    if logo_base64:
        logo_html = f"<img src='{logo_base64}' alt='{brand['logo_text']}' style='max-height: 45px;'>"
    else:
        logo_html = f"<h1>{brand['logo_text']}</h1>"

    html = f"""<!DOCTYPE html>
    <html>
    <head>
    <title>{brand['title']}</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background-color: #f4f7f6; color: #333; }}
        .container {{ max-width: 1100px; margin: 0 auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }}
        .header {{ background-color: {brand['header_bg']}; border-bottom: 4px solid {brand['primary_color']}; color: {brand['header_text']}; padding: 20px 30px; display: flex; justify-content: space-between; align-items: center; }}
        .header h1 {{ margin: 0; font-size: 24px; letter-spacing: 1px; color: {brand['header_text']}; }}
        .header a {{ color: {brand['header_text']}; text-decoration: none; font-size: 14px; opacity: 0.8; transition: opacity 0.2s; font-weight: bold; }}
        .header a:hover {{ opacity: 1; color: {brand['primary_color']}; }}
        .content {{ padding: 30px; }}
        .meta {{ margin-bottom: 25px; font-size: 14px; color: #666; border-bottom: 2px solid #eee; padding-bottom: 15px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 14px; }}
        th, td {{ padding: 15px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background-color: #f8f9fa; font-weight: 600; color: #555; text-transform: uppercase; font-size: 12px; border-top: 1px solid #eee; }}
        tr:hover {{ background-color: #fcfcfc; }}
        .track-btn {{ background-color: {brand['primary_color']}; color: #ffffff !important; padding: 8px 15px; border-radius: 4px; text-decoration: none; font-weight: bold; font-size: 12px; display: inline-block; transition: opacity 0.2s; }}
        .track-btn:hover {{ opacity: 0.8; }}
        .status-badge {{ font-weight: bold; font-size: 13px; }}
        .eta-text {{ font-size: 12px; color: #777; margin-top: 4px; display: block; }}
        .ref-text {{ color: #777; font-size: 12px; margin-top: 4px; display: block; }}
    </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                {logo_html}
                <a href="{brand['link']}" target="_blank">Visit Website &rarr;</a>
            </div>
            <div class="content">
                <div class="meta">
                    <strong>Report Date:</strong> {date_str} <br>
                    <strong>Total Shipments:</strong> {len(df)}
                </div>
                <table>
                    <thead>
                        <tr>
                            <th>Store / Recipient</th>
                            <th>Postcode</th>
                            <th>Service</th>
                            <th>Status & ETA</th>
                            <th>Tracking Action</th>
                        </tr>
                    </thead>
                    <tbody>
    """
    
    for _, row in df.iterrows():
        ref = str(row.get('Customer reference', ''))
        recipient = str(row.get('Business/Recipient name', 'Unknown'))
        
        store_display = f"<strong>{escape(recipient)}</strong>"
        if ref and ref.lower() != 'nan':
            store_display += f"<span class='ref-text'>Ref: {escape(ref)}</span>"

        pc = str(row.get('Postal Code', ''))
        service_raw = str(row.get('Service', ''))
        parcels = str(row.get('Number of parcels', '1'))
        service_display = f"{escape(service_raw)}<span class='ref-text'>({escape(parcels)} Parcel{'s' if parcels != '1' else ''})</span>"
        
        status = str(row.get('Status', 'Unknown'))
        eta_date = str(row.get('Delivery due date', ''))
        eta_time = str(row.get('ETA', ''))
        
        eta_date = "" if eta_date.lower() == 'nan' else eta_date
        eta_time = "" if eta_time.lower() == 'nan' else eta_time
        
        status_color = "#27ae60" if status.lower() == "delivered" else "#e67e22" if "out for delivery" in status.lower() else "#333"
        status_display = f"<span class='status-badge' style='color: {status_color};'>{escape(status)}</span>"
        
        if eta_date or eta_time:
            eta_string = f"{eta_date} {eta_time}".strip()
            status_display += f"<span class='eta-text'>ETA: {escape(eta_string)}</span>"
            
        trk = str(row.get('Shipment number', '')).replace('.0', '')
        if trk.lower() == 'nan': trk = ""
        
        track_link = f"https://www.dhl.com/gb-en/home/tracking.html?tracking-id={trk}&submit=1" if trk else "#"
        track_html = f"<a href='{escape(track_link)}' class='track-btn' target='_blank'>Track {escape(trk)}</a>" if trk else "<em>No Tracking</em>"

        html += f"""
                        <tr>
                            <td>{store_display}</td>
                            <td>{escape(pc)}</td>
                            <td>{service_display}</td>
                            <td>{status_display}</td>
                            <td>{track_html}</td>
                        </tr>
        """
        
    html += """
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    </html>
    """
    return html

# --- INTERFACE ---
left_col, right_col = st.columns([1, 2], gap="large")

with left_col:
    st.subheader("1. Upload Export")
    uploaded_file = st.file_uploader("Upload DHL Dashboard Summary (.csv)", type=["csv", "xlsx"])
    
    if uploaded_file:
        st.success("Dashboard Summary loaded successfully.")

with right_col:
    st.subheader("2. Preview & Generate")
    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
                
            df.columns = [str(c).strip() for c in df.columns]
            
            if 'Accounts' not in df.columns:
                st.error("Error: Could not find the 'Accounts' column in the uploaded file. Please ensure you are uploading the raw Dashboard Summary.")
            else:
                accounts = df['Accounts'].dropna().unique()
                st.write(f"Detected **{len(accounts)}** distinct accounts in this export: {', '.join([str(a) for a in accounts])}")

                # --- SAVE TO HISTORY ---------------------------------------
                # This is where campaign history comes from. Without it the
                # Insights page stays empty and client links have nothing
                # to show.
                with st.expander("💾 Save this export to campaign history", expanded=True):
                    campaigns = list_campaigns()
                    if not campaigns:
                        st.caption(
                            "No campaigns logged yet — add one on the **Campaign Master "
                            "Schedule** page first, then come back to link this export to it."
                        )
                    else:
                        labels = {
                            f"{c['client']} — {c['name']} ({c['id']})": c["id"]
                            for c in campaigns
                        }
                        chosen = st.selectbox("Link these shipments to", list(labels.keys()))
                        st.caption(
                            "Re-uploading a later export for the same campaign refreshes "
                            "delivery status rather than duplicating rows, so it's safe to "
                            "upload again as parcels move."
                        )

                        if st.button("Save to history"):
                            rows = []
                            for _, r in df.iterrows():
                                shipment_no = str(r.get('Shipment number', '')).replace('.0', '').strip()
                                if not shipment_no or shipment_no.lower() == 'nan':
                                    continue
                                rows.append({
                                    "campaign_id": labels[chosen],
                                    "account": str(r.get('Accounts', '')).strip(),
                                    "consignment": shipment_no,
                                    "tracking_number": shipment_no,
                                    "recipient": str(r.get('Business/Recipient name', '')).strip(),
                                    "postcode": str(r.get('Postal Code', '')).strip(),
                                    "service": str(r.get('Service', '')).strip(),
                                    "status": str(r.get('Status', '')).strip(),
                                    "weight": pd.to_numeric(r.get('Weight'), errors='coerce') or 0.0,
                                    "parcels": int(pd.to_numeric(r.get('Number of parcels'), errors='coerce') or 1),
                                    "eta": str(r.get('Delivery due date', '')).strip(),
                                    "dispatch_date": datetime.date.today().isoformat(),
                                })
                            written, skipped = record_shipments(rows)
                            st.success(f"✅ {written} shipments saved to history.")
                            if skipped:
                                st.caption(f"{skipped} rows had no shipment number and were skipped.")
                
                if st.button("Generate Dashboards & CSVs"):
                    with st.spinner("Processing data, embedding logos, and generating files..."):
                        
                        today_str = datetime.datetime.now().strftime("%d %B %Y")
                        zip_buffer = io.BytesIO()
                        
                        tabs = st.tabs([str(acc) for acc in accounts])
                        
                        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                            
                            for idx, account_id in enumerate(accounts):
                                acc_str = str(account_id).strip()
                                group_df = df[df['Accounts'] == account_id]
                                
                                brand_info = BRANDING.get(acc_str, DEFAULT_BRAND)
                                base_filename = f"Tracking_{brand_info['name']}_{datetime.datetime.now().strftime('%Y%m%d')}"
                                
                                # 1. GENERATE AND WRITE HTML
                                html_output = generate_branded_html(group_df, acc_str, today_str)
                                zip_file.writestr(f"{base_filename}.html", html_output)
                                
                                # 2. GENERATE AND WRITE CSV
                                csv_buffer = io.StringIO()
                                group_df.to_csv(csv_buffer, index=False)
                                zip_file.writestr(f"{base_filename}.csv", csv_buffer.getvalue())
                                
                                # Render preview
                                with tabs[idx]:
                                    st.write(f"**Previewing:** {base_filename}.html ({len(group_df)} Shipments)")
                                    components.html(html_output, height=600, scrolling=True)

                        st.success("✅ Tracking Dashboards & CSV Data Generated!")
                        st.download_button(
                            label="⬇️ Download All Files (ZIP)",
                            data=zip_buffer.getvalue(),
                            file_name=f"KEP_Tracking_Data_{datetime.datetime.now().strftime('%Y%m%d')}.zip",
                            mime="application/zip"
                        )
                        
        except Exception as e:
            st.error(f"Error processing the file: {e}")
    else:
        st.info("Upload the raw DHL Dashboard Summary to auto-generate your client-facing HTML dashboards and raw CSV data.")
