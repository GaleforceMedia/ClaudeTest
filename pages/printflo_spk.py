import streamlit as st
import pandas as pd
import datetime

st.set_page_config(page_title="Print Flo SPK Picks", page_icon="🖨️", layout="wide")

# --- UI STYLING ---
st.markdown("""
    <style>
    .metric-card { background-color: #f8f9fa; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; text-align: center; margin-bottom: 20px;}
    .stat-text { color: #004B87; font-size: 32px; font-weight: bold; margin: 0; }
    .stButton>button { background-color: #004B87; color: white; border-radius: 4px; font-weight: bold; padding: 12px; width: 100%; border: none; font-size: 16px;}
    .stButton>button:hover { background-color: #003666; color: white; }
    </style>
    """, unsafe_allow_html=True)

st.title("🖨️ Print Flo (SPK) Pick Lists")
st.write("Upload the Stonegate/Print Flo allocation matrix to automatically generate printable warehouse pick lists.")
st.divider()

# --- HELPER: HTML PICK LIST GENERATOR ---
def generate_pick_list_html(store_data, campaign_name):
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <title>Pick Lists - {campaign_name}</title>
    <style>
        body {{ font-family: 'Arial', sans-serif; padding: 0; margin: 0; color: #000; background-color: #fff; }}
        .no-print {{ text-align: center; padding: 20px; background: #f8f9fa; margin-bottom: 20px; border-bottom: 1px solid #ddd; }}
        .print-btn {{ padding: 12px 24px; background-color: #004B87; color: white; border: none; font-size: 16px; font-weight: bold; border-radius: 4px; cursor: pointer; }}
        .print-btn:hover {{ background-color: #003666; }}
        
        /* PAGE BREAK LOGIC FOR PRINTING */
        .store-page {{ page-break-after: always; padding: 40px; box-sizing: border-box; }}
        .store-page:last-child {{ page-break-after: auto; }}
        
        .header {{ border-bottom: 3px solid #000; padding-bottom: 15px; margin-bottom: 30px; display: flex; justify-content: space-between; align-items: flex-end; }}
        .header h1 {{ margin: 0; font-size: 28px; font-weight: 900; }}
        .header h2 {{ margin: 5px 0 0 0; font-size: 18px; font-weight: normal; color: #555; }}
        .header-meta {{ text-align: right; font-size: 14px; font-weight: bold; }}
        
        .pick-table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 16px; }}
        .pick-table th, .pick-table td {{ border: 1px solid #000; padding: 12px; text-align: left; }}
        .pick-table th {{ background-color: #f2f2f2; font-weight: bold; text-transform: uppercase; }}
        .pick-table td.qty-col {{ text-align: center; font-size: 20px; font-weight: bold; width: 120px; }}
        
        /* GREY OUT LOGIC FOR ZERO PICKS */
        .grey-row td {{ background-color: #f5f5f5; color: #999; }}
        .grey-row td.qty-col {{ color: #ccc; }}
        
        @media print {{
            .no-print {{ display: none !important; }}
            body {{ padding: 0; }}
            @page {{ margin: 1cm; }}
            /* Ensure background colors print for the greyed out rows */
            * {{ -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }}
        }}
    </style>
    </head>
    <body>
        <div class="no-print">
            <button class="print-btn" onclick="window.print()">🖨️ Print All Pick Lists</button>
            <p style="color: #666; font-size: 14px; margin-top: 10px;">Loads 1 store per page. Ensure 'Print Background Graphics' is ticked.</p>
        </div>
    """
    
    date_str = datetime.datetime.now().strftime("%d/%m/%Y")
    
    for store in store_data:
        html += f"""
        <div class="store-page">
            <div class="header">
                <div>
                    <h1>{store['Site']}</h1>
                    <h2>Postcode: {store['Postcode']}</h2>
                </div>
                <div class="header-meta">
                    Campaign: {campaign_name}<br>
                    Date: {date_str}
                </div>
            </div>
            
            <table class="pick-table">
                <thead>
                    <tr>
                        <th>Item Description</th>
                        <th>Version / Allocation</th>
                        <th>Pick Qty</th>
                    </tr>
                </thead>
                <tbody>
        """
        for pick in store['Picks']:
            # Apply the grey-row class if the quantity is 0
            row_class = "grey-row" if pick['Qty'] == 0 else ""
            
            html += f"""
                    <tr class="{row_class}">
                        <td><strong>{pick['Item']}</strong></td>
                        <td>{pick['Version']}</td>
                        <td class="qty-col">{pick['Qty']}</td>
                    </tr>
            """
            
        html += """
                </tbody>
            </table>
        </div>
        """
    html += "</body></html>"
    return html


# --- INTERFACE ---
col_upload, col_summary = st.columns([1, 2], gap="large")

with col_upload:
    st.subheader("1. Upload Matrix")
    uploaded_file = st.file_uploader("Upload Drop Matrix (Excel)", type=["xlsx", "xls"])
    campaign_name = st.text_input("Campaign Name (For header)", value="Stonegate Phase 1")

with col_summary:
    st.subheader("2. Generation Engine")
    
    if uploaded_file:
        try:
            xls = pd.ExcelFile(uploaded_file)
            sheet_choice = st.selectbox("Select Sheet to Process", xls.sheet_names)
            
            if st.button("Generate Printable Pick Lists"):
                raw_df = pd.read_excel(uploaded_file, sheet_name=sheet_choice, header=None)
                
                # --- THE GRID HUNTER ---
                site_col = -1
                postcode_col = -1
                item_header_row = -1
                first_qty_col = -1
                
                for r_idx, row in raw_df.iterrows():
                    for c_idx, cell_val in enumerate(row):
                        val_str = str(cell_val).strip().lower()
                        
                        if val_str == 'new site name':
                            site_col = c_idx
                        elif val_str == 'postcode':
                            postcode_col = c_idx
                        elif val_str == 'qty' and item_header_row == -1:
                            item_header_row = r_idx
                            first_qty_col = c_idx

                if site_col == -1: site_col = 1
                if postcode_col == -1: postcode_col = 7
                
                if item_header_row != -1 and first_qty_col != -1:
                    start_col_idx = first_qty_col - 1
                    data_start_row = item_header_row + 1
                else:
                    item_header_row = 2 
                    start_col_idx = 8
                    data_start_row = 3
                
                # --- EXTRACTION ENGINE ---
                processed_stores = []
                total_items_picked = 0
                
                for idx in range(data_start_row, len(raw_df)):
                    row = raw_df.iloc[idx]
                    
                    site_name = str(row.iloc[site_col]).strip()
                    postcode_val = str(row.iloc[postcode_col]).strip()
                    
                    if pd.isna(site_name) or site_name.lower() == 'nan' or site_name == '':
                        continue
                        
                    picks = []
                    store_active_qty = 0 # Track if this specific store actually gets a box at all
                    
                    for col_i in range(start_col_idx, len(raw_df.columns), 2):
                        if col_i + 1 < len(raw_df.columns):
                            item_name = str(raw_df.iloc[item_header_row, col_i]).strip()
                            
                            if item_name.upper() != 'QTY' and item_name.lower() != 'nan' and item_name != '':
                                version = str(row.iloc[col_i]).strip()
                                qty_raw = str(row.iloc[col_i + 1]).strip()
                                
                                clean_qty = 0
                                display_version = version
                                
                                # Process the quantity
                                if qty_raw.upper() not in ['X', 'NAN', '']:
                                    try:
                                        clean_qty = int(float(qty_raw))
                                    except ValueError:
                                        clean_qty = 0
                                
                                # If quantity is 0 or invalid, standardise the version text
                                if clean_qty == 0 or version.upper() in ['X', 'NAN', '']:
                                    display_version = "N/A"
                                        
                                picks.append({
                                    'Item': item_name,
                                    'Version': display_version,
                                    'Qty': clean_qty
                                })
                                
                                store_active_qty += clean_qty
                    
                    # Only add the store to the print run if they have AT LEAST 1 item to pack
                    if picks and store_active_qty > 0:
                        processed_stores.append({
                            'Site': site_name,
                            'Postcode': postcode_val,
                            'Picks': picks
                        })
                        total_items_picked += store_active_qty
                
                # --- DISPLAY ---
                if processed_stores:
                    m1, m2 = st.columns(2)
                    with m1:
                        st.markdown(f"<div class='metric-card'><h4>Stores to Pack</h4><p class='stat-text'>{len(processed_stores)}</p></div>", unsafe_allow_html=True)
                    with m2:
                        st.markdown(f"<div class='metric-card'><h4>Total Items Picked</h4><p class='stat-text'>{total_items_picked:,}</p></div>", unsafe_allow_html=True)
                    
                    st.success(f"✅ Successfully extracted {len(processed_stores)} store allocations.")
                    
                    html_output = generate_pick_list_html(processed_stores, campaign_name)
                    st.components.v1.html(html_output, height=800, scrolling=True)
                else:
                    st.warning("Could not find any active picks on this sheet. Make sure you selected the correct Drop sheet.")
                    
        except Exception as e:
            st.error(f"Error processing matrix: {e}")
            
    else:
        st.info("👈 Please upload the Stonegate Matrix to begin.")
