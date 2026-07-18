import pandas as pd
from fpdf import FPDF
import sys
import os

def generate_th_picklists(excel_file, output_pdf):
    # --- TIM HORTONS CONFIGURATION MAP ---
    SHEET_NAME = 0 
    
    TYPE_ROW_INDEX = 1       # Row 2 (Product Type: A BOARDS, etc.)
    CODE_ROW_INDEX = 2       # Row 3 (Product Code: C4-ABA1-MANGODRINKS)
    SPEC_ROW_INDEX = 4       # Row 5 (Specs/Dimensions: A1 1pp 3mm Foamex)
    STORE_START_ROW = 5      # Row 6 
    
    POSTCODE_COL = 5         # Column F 
    STORE_NAME_COL = 7       # Column H 
    TIER_COL = 8             # Column I 
    PRODUCT_START_COL = 9    # Column J 

    # Get the clean title from the file name
    base_name = os.path.splitext(os.path.basename(excel_file))[0]
    clean_title = base_name.split('-')[0].strip() if '-' in base_name else base_name

    try:
        df = pd.read_excel(excel_file, sheet_name=SHEET_NAME, header=None)
    except FileNotFoundError:
        print(f"  [!] ERROR: Could not find '{excel_file}'.")
        return

    # 1. Extract the product profiles 
    products = []
    for col_idx in range(PRODUCT_START_COL, len(df.columns)):
        prod_type = df.iloc[TYPE_ROW_INDEX, col_idx]
        code = df.iloc[CODE_ROW_INDEX, col_idx]
        spec = df.iloc[SPEC_ROW_INDEX, col_idx]
        
        if pd.isna(code) or str(code).strip() == "":
            products.append(None)
        else:
            products.append({
                "type": str(prod_type).strip() if not pd.isna(prod_type) else "N/A",
                "code": str(code).strip(),
                "spec": str(spec).strip() if not pd.isna(spec) else ""
            })

    # 2. Parse the Stores
    # List rather than dict: duplicate store names were overwriting
    # each other, so one store lost its pick list entirely.
    store_orders = []
    for index, row in df.iloc[STORE_START_ROW:].iterrows():
        store_name = row[STORE_NAME_COL]
        if pd.isna(store_name) or str(store_name).strip() == "":
            continue
            
        store_name = str(store_name).strip()
        postcode = str(row[POSTCODE_COL]).strip() if not pd.isna(row[POSTCODE_COL]) else ""
        tier = str(row[TIER_COL]).strip() if not pd.isna(row[TIER_COL]) else ""
        
        if tier.endswith(".0"):
            tier = tier[:-2]

        items_for_store = []
        for col_idx, product_info in enumerate(products):
            if product_info is None:
                continue 
                
            actual_col = PRODUCT_START_COL + col_idx
            qty = row[actual_col]
            qty_display = 0 
            
            if not pd.isna(qty):
                qty_str = str(qty).strip()
                if qty_str and qty_str.replace('.', '', 1).isdigit():
                    qty_float = float(qty_str)
                    qty_display = int(qty_float) if qty_float.is_integer() else qty_float
                    
            items_for_store.append({
                "product": product_info,
                "qty": qty_display
            })
                
        if items_for_store:
            store_orders.append((store_name, {
                "postcode": postcode, 
                "tier": tier, 
                "items": items_for_store
            }))

    # 3. Generate the High-Density PDF
    pdf = FPDF()
    pdf.set_auto_page_break(auto=False) 
    
    # --- UPDATED: 2-Line Row Layout Constants (Guarantees max 2 pages) ---
    ITEMS_PER_PAGE = 20      # Increased to fit more items vertically
    ROW_HEIGHT = 11.5        # Condensed height for two text lines
    COL_WIDTH = 190          # Full width of A4 portrait
    X_START = 10             # Left Margin

    for store_name, data in store_orders:
        all_items = data["items"]
        
        chunks = [all_items[i:i + ITEMS_PER_PAGE] for i in range(0, len(all_items), ITEMS_PER_PAGE)]
        global_idx = 1
        
        for page_num, chunk in enumerate(chunks, start=1):
            pdf.add_page()
            
            # --- MASSIVE CENTRAL HEADER ---
            
            # 1. Campaign Title
            pdf.set_font("Arial", size=11, style='B')
            pdf.set_text_color(130, 130, 130)
            page_tag = f" (Page {page_num} of {len(chunks)})" if len(chunks) > 1 else ""
            pdf.cell(0, 6, txt=f"{clean_title.upper()} - PICK LIST{page_tag}", ln=True, align='C')
            pdf.ln(2)
            
            # 2. Store Name
            pdf.set_text_color(0, 0, 0)
            pdf.set_font("Arial", size=24, style='B')
            pdf.cell(0, 10, txt=store_name.upper()[:45], ln=True, align='C')
            
            # 3. Postcode & Tier
            pdf.set_font("Arial", size=14, style='B')
            pc_text = data["postcode"].encode('latin-1', 'replace').decode('latin-1') if data["postcode"] and data["postcode"] != "nan" else ""
            tier_text = f"Tier: {data['tier']}" if data['tier'] else ""
            
            sub_text = ""
            if pc_text and tier_text:
                sub_text = f"{pc_text}    |    {tier_text}"
            elif pc_text:
                sub_text = pc_text
            elif tier_text:
                sub_text = tier_text
                
            pdf.cell(0, 8, txt=sub_text, ln=True, align='C')
            
            # Divider Line
            pdf.ln(3)
            y_grid_start = pdf.get_y()
            pdf.set_draw_color(0, 0, 0)
            pdf.set_line_width(0.5)
            pdf.line(10, y_grid_start, 200, y_grid_start)
            pdf.ln(2)
            
            y_grid_start += 3 

            # --- DRAW THE SINGLE-COLUMN GRID ---
            for relative_idx, item in enumerate(chunk):
                qty = item['qty']
                p = item['product']
                
                x_offset = X_START
                y_offset = y_grid_start + (relative_idx * ROW_HEIGHT)

                # --- THE QTY BOX ---
                qty_box_x = 175
                qty_box_w = 20
                qty_box_y = y_offset + 1.5 
                
                pdf.set_xy(qty_box_x, qty_box_y)
                if qty == 0:
                    pdf.set_fill_color(240, 240, 240) 
                    pdf.rect(qty_box_x, qty_box_y, qty_box_w, 8, 'F')
                    pdf.set_xy(qty_box_x, qty_box_y + 1.5)
                    pdf.set_font("Arial", size=7, style='B')
                    pdf.set_text_color(160, 160, 160)
                    pdf.cell(qty_box_w, 5, "0 (SKIP)", align='C')
                    
                    pdf.set_text_color(160, 160, 160)
                    checkbox = "[-]"
                else:
                    pdf.set_draw_color(0, 0, 0)
                    pdf.set_line_width(0.3)
                    pdf.rect(qty_box_x, qty_box_y, qty_box_w, 8, 'D')
                    pdf.set_xy(qty_box_x, qty_box_y + 1)
                    pdf.set_font("Arial", size=12, style='B')
                    pdf.set_text_color(0, 0, 0)
                    pdf.cell(qty_box_w, 6, str(qty), align='C') 
                    
                    pdf.set_text_color(0, 0, 0)
                    checkbox = "[ ]"

                # --- THE DATA BLOCK ---
                
                # Line 1: Checkbox + Global Idx + CODE (Main focus, larger font)
                pdf.set_xy(x_offset, y_offset)
                pdf.set_font("Arial", size=11, style='B' if qty > 0 else '')
                l1 = f"{checkbox}  {global_idx:02d}  |  {p['code']}"
                pdf.cell(160, 5, txt=l1[:95].encode('latin-1', 'replace').decode('latin-1'), ln=True)
                
                # Line 2: TYPE - SPECIFICATIONS (Combined onto one line)
                pdf.set_xy(x_offset + 8.5, y_offset + 5.5)
                pdf.set_font("Arial", size=8, style='B' if qty > 0 else '')
                
                clean_spec = p['spec'].replace('\n', '  |  ') if p['spec'] and p['spec'].lower() != "nan" else ""
                combined_desc = f"{p['type']}  -  {clean_spec}" if clean_spec else p['type']
                
                pdf.cell(160, 4, txt=combined_desc[:135].encode('latin-1', 'replace').decode('latin-1'), ln=True)

                # --- ROW SEPARATOR ---
                pdf.set_draw_color(225, 225, 225)
                pdf.set_line_width(0.2)
                pdf.line(x_offset, y_offset + ROW_HEIGHT - 1, x_offset + COL_WIDTH, y_offset + ROW_HEIGHT - 1)

                global_idx += 1
            
            pdf.set_text_color(0, 0, 0) 

    pdf.output(output_pdf)
    print(f"  -> Success! Saved to {output_pdf}")

def batch_process():
    excel_files = [f for f in os.listdir('.') if f.endswith('.xlsx') and not f.startswith('~$')]
    
    if not excel_files:
        print("No Excel files found in the current folder to process.")
        return

    print(f"\n--- TIM HORTONS (SINGLE PAGE) BATCH INITIATED ---")
    print(f"Found {len(excel_files)} spreadsheets to process.\n")
    
    for excel_file in excel_files:
        base_name = os.path.splitext(excel_file)[0]
        output_pdf = f"{base_name}.pdf"
        
        print(f"Processing: {excel_file}")
        generate_th_picklists(excel_file, output_pdf)
        
    print("\n--- BATCH COMPLETE ---")

if __name__ == "__main__":
    if len(sys.argv) == 3:
        generate_th_picklists(sys.argv[1], sys.argv[2])
    elif len(sys.argv) == 1:
        batch_process()
    else:
        print("Usage:")
        print("Batch Mode: python3 generate_th_picklists.py")
        print("Single File: python3 generate_th_picklists.py input.xlsx output.pdf")