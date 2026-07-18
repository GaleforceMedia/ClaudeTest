import streamlit as st
import pandas as pd
import tempfile
import os
import zipfile
import io
import shutil
import datetime

# Import our client layouts
from mp_layout import generate_picklists as format_mamas_papas, extract_dhl_data
from th_layout import generate_th_picklists as format_tim_hortons
from cu_layout import generate_cu_picklists as format_craft_union

# --- PAGE SETUP & BRANDING ---
st.set_page_config(page_title="Pick Lists", page_icon="📦", layout="wide")

st.markdown("""
    <style>
    .stButton>button {
        background-color: #000000;
        color: white;
        border-radius: 4px;
        font-weight: bold;
        border: none;
        width: 100%;
        padding: 10px;
    }
    .stButton>button:hover { background-color: #333333; color: white; }
    h1, h2, h3 { font-family: 'Arial', sans-serif; }
    [data-testid="stColumn"]:nth-child(1) {
        background-color: #f8f9fa;
        padding: 20px;
        border-radius: 8px;
        border: 1px solid #e0e0e0;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("📦 KEP Print Group - Pick List Generator")
st.write("Convert raw client spreadsheets into formatted dispatch documents. Upload multiple files to batch process.")
st.divider()

left_col, right_col = st.columns([1, 2], gap="large")

with left_col:
    st.subheader("1. Setup & Upload")
    
    client_option = st.selectbox("Select Layout Mode", ("Tim Hortons", "Mamas & Papas", "PrintFlo - CU"))
    campaign_title = st.text_input("Campaign Title (Prints on PDF)", "Enter Campaign Name...")
    
    # --- M&P CONDITIONAL SETTINGS (IMAGES & DHL) ---
    use_images = False
    image_files = None
    generate_dhl = False
    dhl_ref = ""
    dhl_weight = "3"
    dhl_parcels = 1
    dhl_date = None

    if client_option == "Mamas & Papas":
        st.divider()
        st.write("#### M&P Extra Options")
        
        # 1. Images
        use_images = st.checkbox("Include Product Images (Thumbnails)")
        if use_images:
            st.caption("Upload images named by Column Letter (e.g., J.jpg) or Product Code.")
            image_files = st.file_uploader("Upload Images or .zip", type=["jpg", "jpeg", "png", "zip"], accept_multiple_files=True)
            
        st.write(" ") 
        
        # 2. DHL CSV
        generate_dhl = st.checkbox("Generate DHL Shipping CSV")
        if generate_dhl:
            st.caption("Configure the batch file for DHL.")
            d_col1, d_col2 = st.columns(2)
            with d_col1:
                dhl_date = st.date_input("Dispatch Date", datetime.date.today())
                dhl_ref = st.text_input("Customer Reference", "M&P Campaign")
            with d_col2:
                dhl_weight = st.selectbox("Weight", [f"{i}kg" for i in range(1, 11)], index=2)
                dhl_parcels = st.number_input("Number of Parcels", min_value=1, value=1)
            
    st.divider()
    uploaded_files = st.file_uploader("Upload raw Excel files (.xlsx)", type=["xlsx"], accept_multiple_files=True)

# --- LIVE PREVIEW & GENERATION LOGIC ---
with right_col:
    st.subheader("Data Preview & Generation")
    
    if uploaded_files:
        try:
            first_file = uploaded_files[0]
            raw_df = pd.read_excel(first_file)
            
            st.write(f"**Previewing:** `{first_file.name}` (Showing top 20 rows)")
            st.dataframe(raw_df.head(20), use_container_width=True, height=450)
            
            generate_standard_btn = st.button(f"Generate {client_option} PDFs ({len(uploaded_files)} files)")
            
            if generate_standard_btn:
                if client_option in ["Mamas & Papas", "PrintFlo - CU"] and (campaign_title == "" or campaign_title == "Enter Campaign Name..."):
                     st.warning("Please enter a valid Campaign Title before generating.")
                else:
                    with st.spinner(f'Batch processing {len(uploaded_files)} files using {client_option} layout...'):
                        
                        all_dhl_rows = []
                        temp_image_dir = None
                        
                        if client_option == "Mamas & Papas" and use_images and image_files:
                            temp_image_dir = tempfile.mkdtemp() 
                            for img in image_files:
                                if img.name.lower().endswith('.zip'):
                                    with zipfile.ZipFile(img, 'r') as zip_ref:
                                        zip_ref.extractall(temp_image_dir)
                                else:
                                    with open(os.path.join(temp_image_dir, img.name), "wb") as f:
                                        f.write(img.getvalue())
                        
                        zip_buffer = io.BytesIO()
                        
                        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                            for file in uploaded_files:
                                with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_in, \
                                     tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_out:
                                    
                                    tmp_in.write(file.getvalue())
                                    input_path = tmp_in.name
                                    output_path = tmp_out.name
                                
                                try:
                                    if client_option == "Tim Hortons":
                                        format_tim_hortons(input_path, output_path)
                                        
                                    elif client_option == "Mamas & Papas":
                                        format_mamas_papas(input_path, output_path, campaign_title=campaign_title, image_dir=temp_image_dir)
                                        
                                        # RUN DHL EXTRACTION IF TICKED
                                        if generate_dhl:
                                            w_val = dhl_weight.replace("kg", "")
                                            d_str = dhl_date.strftime("%d/%m/%Y")
                                            rows = extract_dhl_data(input_path, dhl_ref, w_val, dhl_parcels, d_str)
                                            all_dhl_rows.extend(rows)
                                            
                                    elif client_option == "PrintFlo - CU":
                                        format_craft_union(input_path, output_path, campaign_title=campaign_title)
                                        
                                    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                                        clean_name = client_option.replace(' ', '')
                                        pdf_filename = f"KEP_{clean_name}_{file.name.replace('.xlsx', '')}.pdf"
                                        zip_file.write(output_path, arcname=pdf_filename)
                                except Exception as e:
                                    st.error(f"Error processing {file.name}: {e}")
                                finally:
                                    if os.path.exists(input_path): os.remove(input_path)
                                    if os.path.exists(output_path): os.remove(output_path)
                            
                            # --- APPEND DHL CSV TO THE ZIP FILE ---
                            if client_option == "Mamas & Papas" and generate_dhl and all_dhl_rows:
                                df_dhl = pd.DataFrame(all_dhl_rows)
                                cols = ['Account Number', 'Full Name', 'Address 1', 'Address 2', 'Address 3', 'Address 4', 'Postcode', 'Country', 'Email', 'FAO', 'Tel No', 'No of items', 'Weight kg', 'Notes', 'Delivery Email', 'Job Ref', 'Service', 'Dispatch Date']
                                df_dhl = df_dhl.reindex(columns=cols)
                                
                                csv_buffer = io.StringIO()
                                df_dhl.to_csv(csv_buffer, index=False)
                                
                                clean_campaign = campaign_title.replace(' ', '_')
                                zip_file.writestr(f"DHL_Batch_{clean_campaign}.csv", csv_buffer.getvalue())

                        if temp_image_dir and os.path.exists(temp_image_dir):
                            shutil.rmtree(temp_image_dir)
                            
                        st.success(f"✅ Successfully zipped {len(uploaded_files)} files!")
                        clean_zip_name = client_option.replace(' ', '')
                        st.download_button(
                            label="⬇️ Download All PDFs & Shipping Labels (ZIP)",
                            data=zip_buffer.getvalue(),
                            file_name=f"KEP_{clean_zip_name}_PickLists.zip",
                            mime="application/zip"
                        )

        except Exception as e:
            st.error(f"Could not read the Excel file: {e}")
    else:
        st.info("Upload one or more spreadsheets on the left to activate the preview and generation tools.")
