import pandas as pd
from fpdf import FPDF
import sys
import os

def clean_number(val):
    v = str(val).strip()
    if v.endswith('.0'):
        return v[:-2]
    return v

# CHANGED: Added campaign_title argument to accept custom names from the web app
def generate_cu_picklists(excel_file, output_pdf, campaign_title="CRAFT UNION DISPATCH"):
    # --- CRAFT UNION CONFIGURATION MAP ---
    SHEET_NAME = 0 
    
    JOB_ROW_INDEX = 1       # Row 2
    TITLE_ROW_INDEX = 2     # Row 3
    STORE_START_ROW = 3     # Row 4 
    
    BUN_COL = 0             # Column A
    PUB_NAME_COL = 1        # Column B
    POSTCODE_COL = 6        # Column G 
    PRODUCT_START_COL = 8   # Column I 

    try:
        df = pd.read_excel(excel_file, sheet_name=SHEET_NAME, header=None)
    except FileNotFoundError:
        print(f"  [!] ERROR: Could not find '{excel_file}'.")
        return

    # 1. Parse the Products & Versions dynamically
    products = []
    col_idx = PRODUCT_START_COL
    
    while col_idx < len(df.columns):
        job_val = clean_number(df.iloc[JOB_ROW_INDEX, col_idx])
        title_val = str(df.iloc[TITLE_ROW_INDEX, col_idx]).replace('\n', ' ').strip()
        
        if job_val.upper() == "VERSIONS":
            next_col = col_idx + 1
            if next_col < len(df.columns):
                next_job_val = clean_number(df.iloc[JOB_ROW_INDEX, next_col])
                next_title_val = str(df.iloc[TITLE_ROW_INDEX, next_col]).replace('\n', ' ').strip()
                products.append({
                    "type": "versioned",
                    "version_col": col_idx,
                    "qty_col": next_col,
                    "job_num": next_job_val,
                    "title": next_title_val
                })
            col_idx += 2 
        else:
            if job_val != "nan" and job_val != "":
                products.append({
                    "type": "standard",
                    "qty_col": col_idx,
                    "job_num": job_val,
                    "title": title_val
                })
            col_idx += 1

    # 2. Parse the Stores
    # A list, not a dict keyed by name: two pubs can share a name, and
    # keying by name silently dropped one of their pick lists.
    store_orders = []
    for index, row in df.iloc[STORE_START_ROW:].iterrows():
        bun = clean_number(row[BUN_COL]) if not pd.isna(row[BUN_COL]) else ""
        pub_name = str(row[PUB_NAME_COL]).strip() if not pd.isna(row[PUB_NAME_COL]) else ""
        
        if not pub_name or pub_name == "nan":
            continue
            
        postcode = str(row[POSTCODE_COL]).strip() if not pd.isna(row[POSTCODE_COL]) else "N/A"

        items_for_store = []
        for p in products:
            qty_raw = row[p["qty_col"]]
            qty_display = 0 
            
            if not pd.isna(qty_raw):
                qty_str = str(qty_raw).strip()
                if qty_str and qty_str.replace('.', '', 1).isdigit():
                    qty_float = float(qty_str)
                    qty_display = int(qty_float) if qty_float.is_integer() else qty_float
            
            version_text = ""
            if p["type"] == "versioned":
                v_raw = row[p["version_col"]]
                if not pd.isna(v_raw):
                    version_text = str(v_raw).strip()
                    
            items_for_store.append({
                "product": p,
                "qty": qty_display,
                "version": version_text
            })
                
        if items_for_store:
            store_orders.append((pub_name, {
                "bun": bun,
                "postcode": postcode, 
                "items": items_for_store
            }))

    # 3. Generate the PDF
    pdf = FPDF()
    pdf.set_auto_page_break(auto=False) 
    
    ITEMS_PER_PAGE = 30
    ROW_HEIGHT = 8.0   

    for pub_name, data in store_orders:
        all_items = data["items"]
        chunks = [all_items[i:i + ITEMS_PER_PAGE] for i in range(0, len(all_items), ITEMS_PER_PAGE)]
        global_idx = 1
        
        for page_num, chunk in enumerate(chunks, start=1):
            pdf.add_page()
            
            # --- HEADER ---
            pdf.set_font("Arial", size=11, style='B')
            pdf.set_text_color(130, 130, 130)
            page_tag = f" (Page {page_num})" if len(chunks) > 1 else ""
            
            # CHANGED: Injecting the web app title here
            pdf.cell(0, 6, txt=f"{campaign_title.upper()} - PICK LIST{page_tag}", ln=True, align='C')
            pdf.ln(2)
            
            pdf.set_text_color(0, 0, 0)
            pdf.set_font("Arial", size=22, style='B')
            pdf.cell(0, 10, txt=pub_name.upper()[:45], ln=True, align='C')
            
            pdf.set_font("Arial", size=14, style='B')
            bun_text = f"BUN: {data['bun']}" if data['bun'] else "BUN: N/A"
            safe_pc = data['postcode'].encode('latin-1', 'replace').decode('latin-1')
            pdf.cell(0, 8, txt=f"{bun_text}    |    Postcode: {safe_pc}", ln=True, align='C')
            
            pdf.ln(3)
            y_grid_start = pdf.get_y()
            pdf.set_draw_color(0, 0, 0)
            pdf.set_line_width(0.5)
            pdf.line(10, y_grid_start, 200, y_grid_start)
            pdf.ln(2)
            y_grid_start += 3 

            # --- RIGID COLUMN DRAWING ---
            for row_idx, item in enumerate(chunk):
                qty = item['qty']
                p = item['product']
                version = item['version']
                
                y_offset = y_grid_start + (row_idx * ROW_HEIGHT)

                # COL 5: QTY BOX (Far Right)
                qty_box_x = 175
                qty_box_w = 25
                
                pdf.set_xy(qty_box_x, y_offset)
                if qty == 0:
                    pdf.set_fill_color(240, 240, 240) 
                    pdf.rect(qty_box_x, y_offset, qty_box_w, 7, 'F')
                    pdf.set_xy(qty_box_x, y_offset + 1.5)
                    pdf.set_font("Arial", size=7, style='B')
                    pdf.set_text_color(160, 160, 160)
                    pdf.cell(qty_box_w, 4, "0 (SKIP)", align='C')
                    
                    pdf.set_text_color(160, 160, 160)
                    checkbox = "[-]"
                else:
                    pdf.set_draw_color(0, 0, 0)
                    pdf.set_line_width(0.3)
                    pdf.rect(qty_box_x, y_offset, qty_box_w, 7, 'D')
                    pdf.set_xy(qty_box_x, y_offset + 1)
                    pdf.set_font("Arial", size=12, style='B')
                    pdf.set_text_color(0, 0, 0)
                    pdf.cell(qty_box_w, 5, str(qty), align='C') 
                    
                    pdf.set_text_color(0, 0, 0)
                    checkbox = "[ ]"

                # COL 1: CHECKBOX & INDEX
                pdf.set_xy(10, y_offset + 1.5)
                pdf.set_font("Arial", size=10, style='B' if qty > 0 else '')
                pdf.cell(15, 4, txt=f"{checkbox} {global_idx:02d}")
                
                # COL 2: JOB NUMBER
                pdf.set_xy(28, y_offset + 1.5)
                pdf.set_font("Arial", size=9, style='B' if qty > 0 else '')
                job_text = f"Job: {p['job_num']}"[:20] 
                pdf.cell(25, 4, txt=job_text.encode('latin-1', 'replace').decode('latin-1'))

                # COL 3: VERSION (Prefix removed, raw data only)
                pdf.set_xy(53, y_offset + 1.5)
                if p["type"] == "versioned" and version and version != "nan":
                    pdf.set_font("Arial", size=8.5, style='B' if qty > 0 else '')
                    ver_text = str(version)
                    short_ver = ver_text[:30] + ".." if len(ver_text) > 30 else ver_text
                    pdf.cell(45, 4, txt=short_ver.encode('latin-1', 'replace').decode('latin-1'))

                # COL 4: DESCRIPTION
                pdf.set_xy(102, y_offset + 1.5)
                pdf.set_font("Arial", size=8) 
                clean_title = p['title']
                short_title = clean_title[:45] + ".." if len(clean_title) > 45 else clean_title
                pdf.cell(70, 4, txt=short_title.encode('latin-1', 'replace').decode('latin-1'))

                # --- ROW SEPARATOR ---
                pdf.set_draw_color(225, 225, 225)
                pdf.set_line_width(0.2)
                pdf.line(10, y_offset + ROW_HEIGHT, 200, y_offset + ROW_HEIGHT)

                global_idx += 1
            
            pdf.set_text_color(0, 0, 0) 

    pdf.output(output_pdf)
