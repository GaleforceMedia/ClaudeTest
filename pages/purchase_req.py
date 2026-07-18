import streamlit as st
import pandas as pd
import datetime
import os
import streamlit.components.v1 as components
from html import escape

from utils import get_base64_image

st.set_page_config(page_title="Purchase Requisition", page_icon="📝", layout="centered")

# --- DATA LOADER (CACHED FOR SPEED) ---
@st.cache_data
def load_price_list():
    filepath = "KEP OCT 2025.xlsx"
    if os.path.exists(filepath):
        try:
            df = pd.read_excel(filepath)
            df.columns = [str(c).strip() for c in df.columns]
            return df
        except Exception as e:
            st.error(f"Error reading the Excel file: {e}")
            return pd.DataFrame()
    else:
        st.error(f"Database missing: Could not find '{filepath}' in the repository.")
        return pd.DataFrame()

# --- HELPER: HTML POR FORM GENERATOR ---
def generate_por_html(date_str, requester, job_no, qty, product_desc, supplier, unit_cost, logo_b64):
    total_cost = float(qty) * float(unit_cost)
    
    # Use the KEP logo if available, otherwise fallback to text
    if logo_b64:
        header_visual = f"<img src='{logo_b64}' alt='KEP Logo' style='max-height: 70px; margin-bottom: 10px;'>"
    else:
        header_visual = "<h1>KEP PRINT GROUP</h1>"

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <title>KEP POR Form - {job_no}</title>
    <style>
        body {{ font-family: 'Arial', sans-serif; padding: 40px; color: #000; background-color: #fff; }}
        .no-print {{ text-align: center; margin-bottom: 30px; }}
        .print-btn {{ padding: 12px 24px; background-color: #004B87; color: white; border: none; font-size: 16px; font-weight: bold; border-radius: 4px; cursor: pointer; }}
        .print-btn:hover {{ background-color: #003666; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .header h1 {{ margin: 0; font-size: 32px; font-weight: 900; letter-spacing: 2px; }}
        .header h2 {{ margin: 10px 0 30px 0; font-size: 20px; font-weight: normal; }}
        .meta-table {{ width: 50%; margin-bottom: 30px; font-size: 16px; }}
        .meta-table td {{ padding: 8px 0; }}
        .meta-table .label {{ font-weight: bold; width: 200px; }}
        .meta-table .value {{ border-bottom: 1px solid #000; width: 300px; }}
        .main-table {{ width: 100%; border-collapse: collapse; margin-bottom: 40px; font-size: 14px; }}
        .main-table th, .main-table td {{ border: 1px solid #000; padding: 12px; text-align: center; }}
        .main-table th {{ background-color: #f2f2f2; font-weight: bold; text-transform: uppercase; }}
        .main-table td.left-align {{ text-align: left; }}
        .footer {{ font-size: 11px; color: #555; margin-top: 60px; text-align: left; }}
        
        @media print {{
            .no-print {{ display: none !important; }}
            body {{ padding: 0; }}
            @page {{ margin: 1cm; }}
        }}
    </style>
    </head>
    <body>
        <div class="no-print">
            <button class="print-btn" onclick="window.print()">🖨️ Print Requisition Form</button>
            <p style="color: #666; font-size: 14px; margin-top: 10px;">Click the button above or press Ctrl+P / Cmd+P to print or save as PDF.</p>
        </div>

        <div class="header">
            {header_visual}
            <h2>Purchase Order Requisition Form</h2>
        </div>

        <table class="meta-table">
            <tr><td class="label">Date:</td><td class="value">{escape(date_str)}</td></tr>
            <tr><td class="label">Delivery Date Required:</td><td class="value"></td></tr>
            <tr><td class="label">Requested By:</td><td class="value">{escape(requester)}</td></tr>
        </table>

        <table class="main-table">
            <thead>
                <tr>
                    <th style="width: 10%;">Job No.</th>
                    <th style="width: 10%;">Qty.</th>
                    <th style="width: 40%;">Product</th>
                    <th style="width: 15%;">Supplier</th>
                    <th style="width: 10%;">Cost</th>
                    <th style="width: 5%;">Per</th>
                    <th style="width: 10%;">PO Number</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><strong>{escape(job_no)}</strong></td>
                    <td>{qty}</td>
                    <td class="left-align">{escape(product_desc)}</td>
                    <td>{escape(supplier)}</td>
                    <td>£{unit_cost:.2f}</td>
                    <td>Sheet</td>
                    <td></td>
                </tr>
                <tr><td><br></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
                <tr><td><br></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
            </tbody>
        </table>
        
        <div style="text-align: right; font-size: 18px; font-weight: bold; margin-top: -20px; padding-right: 20px;">
            Total Estimated Cost: £{total_cost:.2f}
        </div>

        <div class="footer">
            KEP POR Form - June 2023 - V1 - Approved by SW
        </div>
    </body>
    </html>
    """
    return html

# --- UI STYLING ---
st.markdown("""
    <style>
    .metric-card { background-color: #f8f9fa; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; text-align: center; margin-top: 20px; margin-bottom: 20px;}
    .price-text { color: #004B87; font-size: 32px; font-weight: bold; margin: 0; }
    .stButton>button { background-color: #004B87; color: white; border-radius: 4px; font-weight: bold; padding: 12px; width: 100%; border: none; font-size: 16px;}
    .stButton>button:hover { background-color: #003666; color: white; }
    </style>
    """, unsafe_allow_html=True)

# --- HEADER APP LOGO ---
logo_b64 = get_base64_image("keplogo.svg")
if logo_b64:
    st.markdown(f"<div style='text-align: center; margin-bottom: 20px;'><img src='{logo_b64}' width='250'></div>", unsafe_allow_html=True)
else:
    st.title("📝 Purchase Requisition")

st.markdown("<h3 style='text-align: center; color: #555;'>Material Requisition Generator</h3>", unsafe_allow_html=True)
st.divider()

# Load the data quietly in the background
df = load_price_list()

if not df.empty:
    # 1. Search Bar
    search_query = st.text_input("🔍 Search Material Database (e.g., '5mm foamex', 'XLD20565')", placeholder="Start typing to search...")
    
    if search_query:
        # Combine description columns for a better search
        desc1 = df.get('Description', pd.Series(dtype='str')).fillna('')
        desc2 = df.get('Description 2', pd.Series(dtype='str')).fillna('')
        item_no = df.get('Item No.', pd.Series(dtype='str')).fillna('')
        
        df['Search_Field'] = item_no + " " + desc1 + " " + desc2
        
        # Filter the dataframe
        filtered_df = df[df['Search_Field'].str.lower().str.contains(search_query.lower())]
        
        if not filtered_df.empty:
            # Create a clean dropdown list
            options = filtered_df.apply(
                lambda row: f"{row.get('Item No.', '')} | {row.get('Description', '')} {row.get('Description 2', '')} | £{row.get('Unit Price', 0)}", 
                axis=1
            ).tolist()
            
            selected_option = st.selectbox("Select the exact sheet size and spec:", options)
            
            selected_idx = options.index(selected_option)
            selected_row = filtered_df.iloc[selected_idx]
            
            st.divider()
            
            # 2. Requisition Details Form
            st.markdown("#### Job Details")
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                job_no = st.text_input("KEP Job Number", placeholder="e.g. 353319")
            with col_b:
                qty = st.number_input("Quantity of Sheets", min_value=1, value=1)
            with col_c:
                supplier = st.text_input("Supplier", value="Pyramid Display")

            requester = st.text_input(
                "Requested By",
                value=st.session_state.get("por_requester", ""),
                placeholder="Your name",
                key="por_requester",
            )
            
            # Calculations
            unit_price = float(selected_row.get('Unit Price', 0))
            total_cost = qty * unit_price
            
            st.markdown(f"<div class='metric-card'><h4>Total Material Cost</h4><p class='price-text'>£{total_cost:,.2f}</p></div>", unsafe_allow_html=True)
            
            # 3. Generate the POR Form
            if st.button("Generate POR Form (Printable)"):
                if not job_no:
                    st.error("Please enter a Job Number before generating.")
                elif not requester:
                    st.error("Please enter who this requisition is being requested by.")
                else:
                    today_str = datetime.datetime.now().strftime("%d/%m/%Y")
                    product_string = f"{selected_row.get('Item No.', '')} - {selected_row.get('Description', '')} {selected_row.get('Description 2', '')}"
                    
                    html_output = generate_por_html(
                        date_str=today_str,
                        requester=requester,
                        job_no=job_no,
                        qty=qty,
                        product_desc=product_string,
                        supplier=supplier,
                        unit_cost=unit_price,
                        logo_b64=logo_b64
                    )
                    
                    st.success("✅ Form Generated! Scroll down to preview and print.")
                    st.components.v1.html(html_output, height=800, scrolling=True)

        else:
            st.warning("No materials found matching that search. Check spelling or try a broader term.")
