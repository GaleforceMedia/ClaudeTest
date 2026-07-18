import streamlit as st
import pandas as pd
import io
import datetime

st.set_page_config(page_title="DHL Batch Maker", page_icon="📦", layout="wide")

# --- KEP BRANDING CSS ---
st.markdown("""
    <style>
    .stButton>button { background-color: #000000; color: white; border-radius: 4px; font-weight: bold; padding: 10px; width: 100%; border: none; }
    .stButton>button:hover { background-color: #333333; color: white; }
    h1, h2, h3 { font-family: 'Arial', sans-serif; }
    .preview-table { font-size: 12px; background-color: #f8f9fa; border-radius: 5px; padding: 10px; border: 1px solid #ddd; overflow-x: auto; }
    </style>
    """, unsafe_allow_html=True)

st.title("📦 DHL Batch File Maker")
st.write("Upload any spreadsheet, map the columns, and generate a flawless CSV ready for the DHL bulk upload portal.")
st.divider()

# --- CONFIGURATION DICTIONARIES ---
ACCOUNT_MAP = {
    "F090402 - KEP": "F090402",
    "F181494 - PRINTFLO": "F181494",
    "F199630 - M&P": "F199630"
}

SERVICE_MAP = {
    "Next Day": 1,
    "Next Day Pre 12": 2,
    "Bagit Small 1kg": 40,
    "Bagit Medium 2kg": 30,
    "Bagit Large 5kg": 20
}

# --- LAYOUT ---
col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.subheader("1. Setup & Upload")
    uploaded_file = st.file_uploader("Upload raw address list (.csv or .xlsx)", type=["csv", "xlsx"])

if uploaded_file:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
            
        columns = ["--- Leave Blank ---"] + list(df.columns)
        
        with col1:
            st.divider()
            st.subheader("2. Map DHL Fields")
            
            st.write("**Account & Job Details**")
            acc_choice = st.selectbox("Account Number", list(ACCOUNT_MAP.keys()))
            job_ref = st.text_input("Job Reference (Internal)", "KEP Campaign")
            disp_date = st.date_input("Dispatch Date", datetime.date.today())
            
            st.write("**Service & Parcels**")
            srv_choice = st.selectbox("DHL Service", list(SERVICE_MAP.keys()))
            c_items, c_weight = st.columns(2)
            num_items = c_items.number_input("Number of Items", min_value=1, value=1)
            weight_kg = c_weight.number_input("Weight (kg)", min_value=0.1, value=1.0, step=0.5)
            notes = st.text_input("Notes (Optional)")

            st.write("**Address Mapping (Max 25 chars)**")
            m_name = st.selectbox("Full Name", columns, index=0)
            m_add1 = st.selectbox("Address 1", columns, index=0)
            m_add2 = st.selectbox("Address 2", columns, index=0)
            m_add3 = st.selectbox("Address 3", columns, index=0)
            m_add4 = st.selectbox("Address 4 (Mandatory)", columns, index=0)
            m_pc = st.selectbox("Postcode (Mandatory)", columns, index=0)
            
            st.write("**Contacts & Emails**")
            # FAO Logic
            fao_type = st.radio("FAO Setup", ["Default 'General Manager'", "Map to Spreadsheet"], horizontal=True)
            m_fao = "--- Leave Blank ---"
            if fao_type == "Map to Spreadsheet":
                m_fao = st.selectbox("Map FAO Column", columns, index=0)
                
            # Email Logic
            email_type = st.radio("Email Setup", ["Default 'goodsout@kep.co.uk'", "Map to Spreadsheet"], horizontal=True)
            m_email = "--- Leave Blank ---"
            if email_type == "Map to Spreadsheet":
                m_email = st.selectbox("Map Email Column", columns, index=0)

        # --- DATA PROCESSING FUNCTION ---
        def process_row(row):
            def get_val(col, limit=None):
                if col == "--- Leave Blank ---": return ""
                val = str(row.get(col, "")).strip()
                if val.lower() == 'nan': val = ""
                if limit and val: return val[:limit] # Truncate to limit
                return val

            # Pull and truncate addresses
            name = get_val(m_name, 25)
            add1 = get_val(m_add1, 25)
            add2 = get_val(m_add2, 25)
            add3 = get_val(m_add3, 25)
            add4 = get_val(m_add4, 25)
            pc = get_val(m_pc)
            
            # DHL Mandatory Fallbacks
            if not add4: add4 = "UK" 
            if not pc: pc = "TBA"

            # Contacts
            fao = "General Manager" if fao_type == "Default 'General Manager'" else get_val(m_fao, 25)
            email = "goodsout@kep.co.uk" if email_type == "Default 'goodsout@kep.co.uk'" else get_val(m_email)
            
            return {
                'Account Number': ACCOUNT_MAP[acc_choice],
                'Full Name': name,
                'Address 1': add1,
                'Address 2': add2,
                'Address 3': add3,
                'Address 4': add4,
                'Postcode': pc,
                'Country': 'England',
                'Email': email,
                'FAO': fao,
                'Tel No': '01827280880',
                'No of items': num_items,
                'Weight kg': weight_kg,
                'Notes': notes,
                'Delivery Email': email, 
                'Job Ref': job_ref,
                'Service': SERVICE_MAP[srv_choice],
                'Dispatch Date': disp_date.strftime("%d/%m/%Y")
            }

        # --- LIVE PREVIEW & DOWNLOAD ---
        with col2:
            st.subheader("3. Live Preview")
            
            # Generate the preview for the first row only
            if len(df) > 0:
                first_row_data = process_row(df.iloc[0])
                preview_df = pd.DataFrame([first_row_data])
                
                st.write("This is exactly how your first row will format into DHL:")
                st.dataframe(preview_df.T, use_container_width=True)
                
                st.write(" ")
                if st.button(f"Generate Batch File ({len(df)} rows)", use_container_width=True):
                    with st.spinner("Compiling DHL data..."):
                        # Process all rows
                        all_rows = [process_row(row) for index, row in df.iterrows()]
                        final_df = pd.DataFrame(all_rows)
                        
                        # Ensure exact DHL Column Order
                        dhl_cols = ['Account Number', 'Full Name', 'Address 1', 'Address 2', 'Address 3', 'Address 4', 'Postcode', 'Country', 'Email', 'FAO', 'Tel No', 'No of items', 'Weight kg', 'Notes', 'Delivery Email', 'Job Ref', 'Service', 'Dispatch Date']
                        final_df = final_df[dhl_cols]
                        
                        csv_buffer = io.StringIO()
                        final_df.to_csv(csv_buffer, index=False)
                        
                        safe_ref = job_ref.replace(" ", "_")
                        
                        st.success("✅ DHL Batch File compiled successfully!")
                        st.download_button(
                            label="⬇️ Download DHL CSV",
                            data=csv_buffer.getvalue(),
                            file_name=f"DHL_{safe_ref}_{disp_date.strftime('%d-%m-%Y')}.csv",
                            mime="text/csv"
                        )
            else:
                st.warning("The uploaded spreadsheet appears to be empty.")
                
    except Exception as e:
        st.error(f"Error processing file: {e}")
else:
    with col2:
        st.info("Upload a spreadsheet on the left to activate the live mapping preview.")
