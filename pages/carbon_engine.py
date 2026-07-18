import streamlit as st
import pandas as pd
import io
import zipfile
import datetime
import streamlit.components.v1 as components
from html import escape

from utils import BRANDING, DEFAULT_BRAND, get_base64_image

st.set_page_config(page_title="Carbon Impact Engine", page_icon="🌱", layout="wide")

# --- UI STYLING ---
st.markdown("""
    <style>
    .metric-card { background-color: #f8f9fa; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; text-align: center; margin-bottom: 20px; }
    .eco-text { color: #27ae60; font-size: 32px; font-weight: bold; margin: 0; }
    .stButton>button { background-color: #27ae60; color: white; border-radius: 4px; font-weight: bold; padding: 10px; width: 100%; border: none; }
    .stButton>button:hover { background-color: #219653; color: white; }
    h1, h2, h3 { font-family: 'Arial', sans-serif; }
    </style>
    """, unsafe_allow_html=True)

st.title("🌱 Carbon Impact & ESG Engine")
st.write("Upload the DHL Dashboard Summary. The system calculates Scope 3 emissions (downstream distribution) and generates client-ready sustainability reports.")
st.divider()

# --- HELPER: HTML GENERATOR ---
def generate_esg_html(df, brand_code, date_str, total_co2, total_weight, total_parcels):
    # Shared BRANDING is worded for dispatch reports; this page issues
    # sustainability reports, so retitle per client and use a green accent
    # for the unbranded fallback.
    brand = dict(BRANDING.get(brand_code, DEFAULT_BRAND))
    brand['title'] = f"{brand['name'].replace('_', ' ')} Sustainability Report"
    if brand_code not in BRANDING:
        brand['primary_color'] = "#27ae60"
        brand['header_bg'] = "#27ae60"
        brand['logo_text'] = "ESG Dispatch Reporting"

    logo_base64 = get_base64_image(brand.get('logo_file', '')) if brand.get('logo_file') else None
    
    if logo_base64:
        logo_html = f"<img src='{logo_base64}' alt='{escape(brand['logo_text'])}' style='max-height: 45px;'>"
    else:
        logo_html = f"<h1>{escape(brand['logo_text'])}</h1>"

    # ESG Equivalent Metrics
    miles_driven = int(total_co2 / 0.28) # Avg UK car emits ~0.28kg per mile
    trees_needed = round(total_co2 / 21, 1) # A mature tree absorbs ~21kg of CO2 per year

    html = f"""<!DOCTYPE html>
    <html>
    <head>
    <title>{escape(brand['title'])}</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background-color: #f4f7f6; color: #333; }}
        .container {{ max-width: 1000px; margin: 0 auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }}
        .header {{ background-color: {brand['header_bg']}; border-bottom: 4px solid #27ae60; color: {brand['header_text']}; padding: 20px 30px; display: flex; justify-content: space-between; align-items: center; }}
        .header h1 {{ margin: 0; font-size: 24px; letter-spacing: 1px; color: {brand['header_text']}; }}
        .content {{ padding: 30px; }}
        .summary-box {{ display: flex; justify-content: space-between; background-color: #f0fdf4; border: 1px solid #bbf7d0; padding: 20px; border-radius: 8px; margin-bottom: 30px; }}
        .metric {{ text-align: center; width: 30%; }}
        .metric h3 {{ margin: 0; font-size: 14px; color: #166534; text-transform: uppercase; }}
        .metric p {{ margin: 10px 0 0 0; font-size: 28px; font-weight: bold; color: #15803d; }}
        .equivalencies {{ text-align: center; font-size: 14px; color: #555; margin-bottom: 30px; font-style: italic; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 14px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background-color: #f8f9fa; font-weight: 600; color: #555; text-transform: uppercase; font-size: 12px; }}
        tr:hover {{ background-color: #fcfcfc; }}
        .co2-text {{ color: #27ae60; font-weight: bold; }}
    </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                {logo_html}
                <div style="font-weight: bold; color: {brand['header_text']};">Scope 3 Emission Report</div>
            </div>
            <div class="content">
                <div style="margin-bottom: 20px; font-size: 14px; color: #666;">
                    <strong>Report Period:</strong> {date_str} <br>
                    <strong>Methodology:</strong> Emissions estimated using standard UK freight proxy factors (Base drop + volumetric weight).
                </div>
                
                <div class="summary-box">
                    <div class="metric">
                        <h3>Total Shipments</h3>
                        <p>{total_parcels}</p>
                    </div>
                    <div class="metric">
                        <h3>Total Freight Weight</h3>
                        <p>{total_weight:,.1f} kg</p>
                    </div>
                    <div class="metric">
                        <h3>Est. CO2e Emissions</h3>
                        <p>{total_co2:,.1f} kg</p>
                    </div>
                </div>

                <div class="equivalencies">
                    🌱 This carbon footprint is equivalent to driving a standard UK car for <strong>{miles_driven:,} miles</strong>, or the annual carbon absorption of <strong>{trees_needed} mature trees</strong>.
                </div>

                <table>
                    <thead>
                        <tr>
                            <th>Recipient</th>
                            <th>Postcode</th>
                            <th>Weight (kg)</th>
                            <th>Service</th>
                            <th>Est. CO2e (kg)</th>
                        </tr>
                    </thead>
                    <tbody>
    """
    
    for _, row in df.iterrows():
        recipient = str(row.get('Business/Recipient name', 'Unknown'))
        pc = str(row.get('Postal Code', ''))
        service = str(row.get('Service', ''))
        weight = float(row.get('Weight', 0))
        co2 = float(row.get('Est_CO2_kg', 0))
        
        html += f"""
                        <tr>
                            <td>{escape(recipient)}</td>
                            <td>{escape(pc)}</td>
                            <td>{weight:.1f}</td>
                            <td>{escape(service)}</td>
                            <td class="co2-text">{co2:.2f} kg</td>
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
    st.subheader("1. ESG Configuration")
    uploaded_file = st.file_uploader("Upload DHL Dashboard Summary (.csv)", type=["csv", "xlsx"])
    
    st.divider()
    st.write("**Emission Proxy Settings**")
    st.write("Adjust these sliders based on your courier's latest ESG documentation.")
    
    base_emission = st.slider("Base CO2 per delivery stop (kg)", min_value=0.10, max_value=1.00, value=0.35, step=0.05, help="The baseline carbon emitted just for the van to stop at a location.")
    weight_factor = st.slider("CO2 multiplier per kg of weight", min_value=0.01, max_value=0.20, value=0.05, step=0.01, help="The extra carbon emitted based on the physical weight of the print.")

if uploaded_file:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
            
        df.columns = [str(c).strip() for c in df.columns]
        
        if 'Accounts' not in df.columns or 'Weight' not in df.columns:
            st.error("Error: Could not find 'Accounts' or 'Weight' columns. Ensure this is the DHL Dashboard Summary.")
        else:
            # Data Cleaning for Math Operations
            df['Weight'] = pd.to_numeric(df['Weight'], errors='coerce').fillna(1.0)
            df['Number of parcels'] = pd.to_numeric(df['Number of parcels'], errors='coerce').fillna(1.0)
            
            # --- THE CARBON ALGORITHM ---
            df['Est_CO2_kg'] = (df['Number of parcels'] * base_emission) + (df['Weight'] * weight_factor)
            
            total_co2 = df['Est_CO2_kg'].sum()
            total_weight = df['Weight'].sum()
            
            with right_col:
                st.subheader("2. Carbon Impact Overview")
                m1, m2 = st.columns(2)
                with m1:
                    st.markdown(f"<div class='metric-card'><h4>Total Freight Weight</h4><p class='eco-text'>{total_weight:,.1f} kg</p></div>", unsafe_allow_html=True)
                with m2:
                    st.markdown(f"<div class='metric-card'><h4>Total CO2e Emitted</h4><p class='eco-text'>{total_co2:,.2f} kg</p></div>", unsafe_allow_html=True)
                
                accounts = df['Accounts'].dropna().unique()
                
                if st.button("Generate Client ESG Reports"):
                    with st.spinner("Compiling sustainability data..."):
                        today_str = datetime.datetime.now().strftime("%d %B %Y")
                        zip_buffer = io.BytesIO()
                        
                        tabs = st.tabs([str(acc) for acc in accounts])
                        
                        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                            for idx, account_id in enumerate(accounts):
                                acc_str = str(account_id).strip()
                                group_df = df[df['Accounts'] == account_id]
                                
                                acc_co2 = group_df['Est_CO2_kg'].sum()
                                acc_weight = group_df['Weight'].sum()
                                acc_parcels = len(group_df)
                                
                                brand_info = BRANDING.get(acc_str, DEFAULT_BRAND)
                                base_filename = f"ESG_Impact_{brand_info['name']}_{datetime.datetime.now().strftime('%Y%m%d')}"
                                
                                html_output = generate_esg_html(group_df, acc_str, today_str, acc_co2, acc_weight, acc_parcels)
                                zip_file.writestr(f"{base_filename}.html", html_output)
                                
                                with tabs[idx]:
                                    components.html(html_output, height=600, scrolling=True)

                        st.success("✅ Sustainability Reports Generated!")
                        st.download_button(
                            label="⬇️ Download All ESG Reports (ZIP)",
                            data=zip_buffer.getvalue(),
                            file_name=f"KEP_ESG_Reports_{datetime.datetime.now().strftime('%Y%m%d')}.zip",
                            mime="application/zip"
                        )
                        
    except Exception as e:
        st.error(f"Error processing the file: {e}")
else:
    with right_col:
        st.info("Upload the DHL Dashboard Summary to calculate the carbon footprint of your shipments.")
