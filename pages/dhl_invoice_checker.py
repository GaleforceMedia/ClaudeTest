import streamlit as st
import pandas as pd
import urllib.parse

st.set_page_config(page_title="Invoice Reconciler", page_icon="🧾", layout="wide")

# --- KEP BRANDING CSS ---
st.markdown("""
    <style>
    .metric-card { background-color: #f8f9fa; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; text-align: center; }
    .price-text { color: #004B87; font-size: 32px; font-weight: bold; margin: 0; }
    .alert-text { color: #d9534f; font-size: 32px; font-weight: bold; margin: 0; }
    .dispute-btn { background-color: #004B87; color: white; text-align: center; display: inline-block; border-radius: 4px; font-weight: bold; padding: 12px; width: 100%; border: none; text-decoration: none; font-family: Arial, sans-serif; }
    .dispute-btn:hover { background-color: #003666; color: white; }
    </style>
    """, unsafe_allow_html=True)

st.title("🧾 Courier Invoice Reconciler")
st.write("Upload a raw DHL invoice (CSV). The system will map service codes, fix number formatting, and auto-draft a verification email for unexpected surcharges.")
st.divider()

# --- DHL SERVICE CODE MAPPING ---
DHL_CODES = {
    1: "Parcels - Next Day", 220: "Parcels - Next Day (Neighbor)", 210: "Parcels - Next Day (Safe)",
    2: "Parcels - Pre 12:00", 221: "Parcels - Pre 12:00 (Neighbor)", 211: "Parcels - Pre 12:00 (Safe)",
    9: "Parcels - Pre 10:30", 222: "Parcels - Pre 10:30 (Neighbor)", 212: "Parcels - Pre 10:30 (Safe)",
    3: "Parcels - Pre 09:00",
    4: "Parcels - Saturday", 225: "Parcels - Saturday (Neighbor)", 215: "Parcels - Saturday (Safe)",
    7: "Parcels - Saturday Pre 10:30", 226: "Parcels - Saturday Pre 10:30 (Neighbor)", 216: "Parcels - Saturday Pre 10:30 (Safe)",
    5: "Parcels - Saturday Pre 09:00",
    48: "Parcels - 48 Hours", 72: "Parcels - 72 Hours",
    40: "Bagit Small 1kg - Next Day", 240: "Bagit Small 1kg - Next Day (Neighbor)", 230: "Bagit Small 1kg - Next Day (Safe)",
    41: "Bagit Small 1kg - Pre 12:00", 241: "Bagit Small 1kg - Pre 12:00 (Neighbor)", 231: "Bagit Small 1kg - Pre 12:00 (Safe)",
    49: "Bagit Small 1kg - Pre 10:30", 242: "Bagit Small 1kg - Pre 10:30 (Neighbor)", 232: "Bagit Small 1kg - Pre 10:30 (Safe)",
    42: "Bagit Small 1kg - Pre 09:00",
    30: "Bagit Medium 2kg - Next Day", 250: "Bagit Medium 2kg - Next Day (Neighbor)", 340: "Bagit Medium 2kg - Next Day (Safe)",
    31: "Bagit Medium 2kg - Pre 12:00", 251: "Bagit Medium 2kg - Pre 12:00 (Neighbor)", 341: "Bagit Medium 2kg - Pre 12:00 (Safe)",
    20: "Bagit Large 5kg - Next Day", 260: "Bagit Large 5kg - Next Day (Neighbor)", 360: "Bagit Large 5kg - Next Day (Safe)",
    21: "Bagit Large 5kg - Pre 12:00", 261: "Bagit Large 5kg - Pre 12:00 (Neighbor)", 361: "Bagit Large 5kg - Pre 12:00 (Safe)"
}

uploaded_file = st.file_uploader("Upload DHL Invoice (.csv)", type=["csv"])

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file)
        df.columns = [str(c).strip() for c in df.columns]

        required_cols = ['Consignment', 'Invoice', 'Service', 'Value', 'Long Length Charge', 'Heavy Weight Surcharge']
        missing = [col for col in required_cols if col not in df.columns]
        
        if missing:
            st.error(f"Missing expected columns from DHL Invoice: {', '.join(missing)}")
        else:
            # Force Consignment to be treated as a pure string
            df['Consignment'] = df['Consignment'].astype(str).str.replace(r'\.0', '', regex=True)

            # Data Processing
            df['Value'] = pd.to_numeric(df['Value'], errors='coerce').fillna(0.0)
            df['Long Length Charge'] = pd.to_numeric(df['Long Length Charge'], errors='coerce').fillna(0.0)
            df['Heavy Weight Surcharge'] = pd.to_numeric(df['Heavy Weight Surcharge'], errors='coerce').fillna(0.0)
            
            df['Total Surcharges'] = df['Long Length Charge'] + df['Heavy Weight Surcharge']
            if 'Congestion Charge' in df.columns:
                df['Congestion Charge'] = pd.to_numeric(df['Congestion Charge'], errors='coerce').fillna(0.0)
                df['Total Surcharges'] += df['Congestion Charge']
                
            surcharge_mask = df['Total Surcharges'] > 0
            surcharge_df = df[surcharge_mask]
            
            df['Mapped Service'] = df['Service'].apply(lambda x: DHL_CODES.get(x, f"Unknown Code ({x})"))
            
            # --- DASHBOARD METRICS ---
            total_invoice_cost = df['Value'].sum() + df['Total Surcharges'].sum()
            total_surcharge_cost = df['Total Surcharges'].sum()
            total_consignments = df['Consignment'].nunique()
            
            st.subheader("Invoice Overview")
            m1, m2, m3 = st.columns(3)
            with m1:
                st.markdown(f"<div class='metric-card'><h4>Total Consignments</h4><p class='price-text'>{total_consignments}</p></div>", unsafe_allow_html=True)
            with m2:
                st.markdown(f"<div class='metric-card'><h4>Total Invoice Value</h4><p class='price-text'>£{total_invoice_cost:,.2f}</p></div>", unsafe_allow_html=True)
            with m3:
                alert_class = "alert-text" if total_surcharge_cost > 0 else "price-text"
                st.markdown(f"<div class='metric-card'><h4>Hidden Surcharges</h4><p class='{alert_class}'>£{total_surcharge_cost:,.2f}</p></div>", unsafe_allow_html=True)

            st.divider()

            # --- SURCHARGE AUDIT & COLLABORATIVE EMAIL ---
            if not surcharge_df.empty:
                col_left, col_right = st.columns([3, 1])
                with col_left:
                    st.warning(f"⚠️ Found {len(surcharge_df)} shipments with additional surcharges. Use the button to ask DHL to double-check these.")
                
                with col_right:
                    # Generate the collaborative Mailto link body
                    subject = urllib.parse.quote(f"Invoice Verification - KEP Print Group (Inv: {df['Invoice'].iloc[0]})")
                    
                    email_body = "Hi Team,\n\n"
                    email_body += "Could you please help us double-check a few consignments on our recent invoice? We noticed some Long Length and Heavy Weight surcharges applied to the shipments below.\n\n"
                    email_body += "Would you mind verifying that these surcharges are accurate on your end before we clear this invoice for payment? We just want to make sure the dimensions/weights logged in the system match up.\n\n"
                    email_body += "Here are the consignments:\n\n"
                    
                    for idx, row in surcharge_df.iterrows():
                        weight_str = f"{row['Weight']}kg" if 'Weight' in row else "Unknown"
                        weight_type = row.get('Weight Type', 'Unknown')
                        email_body += f"• Consignment: {row['Consignment']} | Ref: {row.get('Reference', '')} | Billed Weight: {weight_str} ({weight_type}) | Surcharge: £{row['Total Surcharges']:.2f}\n"
                    
                    email_body += "\nThanks for your help,\nKEP Print Group"
                    encoded_body = urllib.parse.quote(email_body)
                    mailto_link = f"mailto:billing@dhl.com?subject={subject}&body={encoded_body}"
                    
                    # Changed button to KEP Blue to look more friendly/standard rather than red/alert
                    st.markdown(f'<a href="{mailto_link}" target="_blank" class="dispute-btn">✉️ Email DHL to Double-Check</a>', unsafe_allow_html=True)

                # Show the filtered table to the CSR
                display_cols = ['Consignment', 'Reference', 'Address', 'Mapped Service', 'Weight', 'Weight Type', 'Value', 'Long Length Charge', 'Heavy Weight Surcharge', 'Total Surcharges']
                existing_disp_cols = [c for c in display_cols if c in surcharge_df.columns]
                
                st.dataframe(surcharge_df[existing_disp_cols].sort_values(by="Total Surcharges", ascending=False), use_container_width=True, hide_index=True)
            else:
                st.success("✅ Clean Invoice! No Long Length or Heavy Weight Surcharges detected in this batch.")
            
            st.divider()

            # --- SERVICE BREAKDOWN ---
            st.subheader("Cost Breakdown by Mapped Service")
            breakdown = df.groupby('Mapped Service').agg(
                Shipments=('Consignment', 'count'),
                Total_Base_Cost=('Value', 'sum'),
                Total_Surcharges=('Total Surcharges', 'sum')
            ).reset_index()
            
            breakdown['Final_Cost'] = breakdown['Total_Base_Cost'] + breakdown['Total_Surcharges']
            breakdown = breakdown.sort_values('Final_Cost', ascending=False)
            
            st.dataframe(breakdown, use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"Could not read the invoice: {e}")
