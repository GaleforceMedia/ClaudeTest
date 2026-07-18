import streamlit as st
import pandas as pd
import io
import os
import zipfile
import streamlit.components.v1 as components
from html import escape

st.set_page_config(page_title="PrintFlo Stock Orders", page_icon="📊", layout="wide")

# --- KEP BRANDING CSS ---
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

st.title("📊 PrintFlo & Call-Off Pick Lists")
st.write("Upload PrintFlo CSV or Excel files to automatically generate visual HTML pick lists and formatted Excel sheets.")
st.divider()

# --- BACKEND LOGIC: Generate HTML & Excel ---
# Added 'title_name' as an argument to inject the spreadsheet name
def generate_printflo_files(df, title_name):
    # 1. Clean up address columns so we don't get "nan" printed
    addr_cols = ['DeliveryAddress1', 'DeliveryAddress2', 'DeliveryAddress3', 'DeliveryTown', 'DeliveryCounty', 'DeliveryPostCode']
    existing_addr = [c for c in addr_cols if c in df.columns]
    df[existing_addr] = df[existing_addr].fillna('')

    # 2. Build the HTML String dynamically with the title_name
    html = f"<!DOCTYPE html>\n<html>\n<head>\n<title>{title_name}</title>\n"
    html += "<style>\n"
    html += "body { font-family: Arial, sans-serif; margin: 20px; background-color: #f9f9f9; }\n"
    html += "h1 { color: #333; text-align: center; border-bottom: 2px solid #ccc; padding-bottom: 10px; }\n"
    html += ".order { background: #fff; border: 1px solid #ccc; margin-bottom: 30px; padding: 20px; border-radius: 8px; page-break-inside: avoid; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }\n"
    html += ".order h2 { margin-top: 0; color: #2c3e50; font-size: 20px; border-bottom: 1px solid #eee; padding-bottom: 10px; }\n"
    html += ".address { margin-bottom: 15px; font-size: 15px; color: #444; line-height: 1.4; }\n"
    html += "table { width: 100%; border-collapse: collapse; margin-top: 15px; }\n"
    html += "th, td { border: 1px solid #ddd; padding: 12px; text-align: left; vertical-align: middle; }\n"
    html += "th { background-color: #f1f1f1; font-weight: bold; color: #333; }\n"
    html += ".product-img { max-height: 90px; max-width: 90px; border-radius: 4px; object-fit: contain; }\n"
    html += ".qty-cell { font-size: 18px; font-weight: bold; text-align: center; }\n"
    html += "@media print { body { background-color: white; margin: 0; } .order { box-shadow: none; border: none; border-bottom: 2px dashed #ccc; padding-bottom: 40px; margin-bottom: 40px; page-break-inside: avoid; } }\n"
    html += "</style>\n</head>\n<body>\n"
    
    # Injecting the title onto the printed page header
    html += f"<h1>{escape(title_name)}</h1>\n"

    # Group by OrderId and VenueName
    if 'OrderId' in df.columns and 'VenueName' in df.columns:
        grouped = df.groupby(['OrderId', 'VenueName'])

        for (order_id, venue_name), group in grouped:
            # Safely grab address from the first row of the group
            first_row = group.iloc[0]
            address_parts = []
            for col in addr_cols:
                if col in first_row and str(first_row[col]).strip() != '' and str(first_row[col]).strip().lower() != 'nan':
                    address_parts.append(str(first_row[col]).strip())
            
            address_html = "<br>".join(escape(part) for part in address_parts)
            
            html += f"<div class='order'>\n<h2>Order ID: {escape(str(order_id))} | Venue: {escape(str(venue_name))}</h2>\n"
            if address_html:
                html += f"<div class='address'><strong>Delivery Address:</strong><br>{address_html}</div>\n"
            
            html += "<table>\n"
            html += "<tr>\n<th width=\"110\">Image</th>\n<th width=\"180\">SKU</th>\n<th>Item Name</th>\n<th width=\"100\" style=\"text-align:center;\">Quantity</th>\n</tr>\n"
            
            for index, row in group.iterrows():
                sku = row.get('SKU', '')
                # Handle either ItemName or Name depending on the export
                name = row.get('ItemName', row.get('Name', ''))
                qty = row.get('Qty', '')
                
                # Handle either ProductImageURL or ImageURL
                img_url = row.get('ProductImageURL', row.get('ImageURL', ''))
                
                img_tag = f"<img src='{escape(str(img_url))}' class='product-img'>" if pd.notna(img_url) and str(img_url).startswith('http') else "<em>No Image</em>"
                
                html += f"<tr>\n<td>{img_tag}</td>\n<td>{escape(str(sku))}</td>\n<td>{escape(str(name))}</td>\n<td class=\"qty-cell\">{escape(str(qty))}</td>\n</tr>\n"
                
            html += "</table>\n</div>\n"
            
    html += "</body>\n</html>"

    # 3. Build the Excel Data
    df_excel = df.copy()
    
    image_col = 'ProductImageURL' if 'ProductImageURL' in df_excel.columns else 'ImageURL'
    if image_col in df_excel.columns:
        df_excel['Product Image Preview'] = df_excel[image_col].apply(
            lambda x: f'=IMAGE("{x}")' if pd.notna(x) and str(x).startswith('http') else ''
        )

    desired_cols = ['OrderId', 'VenueName', 'DeliveryAddress1', 'DeliveryAddress2', 'DeliveryTown', 'DeliveryPostCode', 'SKU', 'Name', 'Qty', 'Product Image Preview']
    output_cols = [col for col in desired_cols if col in df_excel.columns]

    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        df_excel[output_cols].to_excel(writer, index=False)

    return html, excel_buffer.getvalue()

# --- INTERFACE ---
left_col, right_col = st.columns([1, 2], gap="large")

with left_col:
    st.subheader("1. Upload Data")
    uploaded_files = st.file_uploader("Upload PrintFlo Data (.csv or .xlsx)", type=["csv", "xlsx"], accept_multiple_files=True)

with right_col:
    st.subheader("2. Preview & Generate")
    if uploaded_files:
        if st.button(f"Generate Files for {len(uploaded_files)} Uploads"):
            with st.spinner("Processing PrintFlo data..."):
                
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    
                    for file in uploaded_files:
                        try:
                            if file.name.endswith('.csv'):
                                df = pd.read_csv(file)
                            else:
                                df = pd.read_excel(file)
                        except Exception as e:
                            st.error(f"Error reading {file.name}: {e}")
                            continue

                        # Extract the filename without the .csv or .xlsx extension
                        base_name = os.path.splitext(file.name)[0]
                        
                        # Pass the base_name into the generation function
                        html_string, excel_bytes = generate_printflo_files(df, title_name=base_name)
                        
                        html_name = f"PickList_{base_name}.html"
                        excel_name = f"PickList_{base_name}.xlsx"

                        zip_file.writestr(html_name, html_string)
                        zip_file.writestr(excel_name, excel_bytes)
                        
                        if file == uploaded_files[0]:
                            st.success(f"Previewing first file: {html_name}")
                            components.html(html_string, height=600, scrolling=True)

                st.success("✅ All files processed and zipped!")
                st.download_button(
                    label="⬇️ Download Pick Lists & Spreadsheets (ZIP)",
                    data=zip_buffer.getvalue(),
                    file_name="KEP_PrintFlo_Stock_Orders.zip",
                    mime="application/zip"
                )
    else:
        st.info("Upload your Call Off CSVs or Excel files on the left to generate visual pick lists.")
