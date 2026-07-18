import streamlit as st
import pandas as pd
from fpdf import FPDF
import io

st.set_page_config(page_title="Label Maker", page_icon="🏷️", layout="wide")

# --- KEP BRANDING CSS ---
st.markdown("""
    <style>
    .stButton>button { background-color: #000000; color: white; border-radius: 4px; font-weight: bold; padding: 10px; width: 100%; border: none; }
    .stButton>button:hover { background-color: #333333; color: white; }
    h1, h2, h3 { font-family: 'Arial', sans-serif; }
    .preview-box { border: 2px dashed #004B87; border-radius: 8px; padding: 20px; background-color: white; margin-top: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

st.title("🏷️ Bulk Label Maker")
st.write("Upload a spreadsheet, map your columns, and generate perfectly aligned PDFs for standard Avery label sheets.")
st.divider()

# --- PRECISE AVERY MEASUREMENTS (in mm) ---
TEMPLATES = {
    "21-Up (L7060 / L7160) | 63.5 x 38.1mm": {
        "cols": 3, "rows": 7,
        "margin_top": 15.1, "margin_left": 7.2,
        "label_width": 63.5, "label_height": 38.1,
        "pitch_x": 66.0, "pitch_y": 38.1
    },
    "10-Up (L7173) | 99.1 x 57.0mm": {
        "cols": 2, "rows": 5,
        "margin_top": 6.0, "margin_left": 4.6,
        "label_width": 99.1, "label_height": 57.0,
        "pitch_x": 101.6, "pitch_y": 57.0
    },
    "2-Up (L7068 / L7168) | 199.6 x 143.5mm": {
        "cols": 1, "rows": 2,
        "margin_top": 5.0, "margin_left": 5.2,
        "label_width": 199.6, "label_height": 143.5,
        "pitch_x": 199.6, "pitch_y": 143.5
    },
    "1-Up (L7167) | 199.6 x 289.1mm": {
        "cols": 1, "rows": 1,
        "margin_top": 4.0, "margin_left": 5.2,
        "label_width": 199.6, "label_height": 289.1,
        "pitch_x": 199.6, "pitch_y": 289.1
    }
}

top_col1, top_col2 = st.columns([1, 1], gap="large")

with top_col1:
    st.subheader("1. Setup & Mapping")
    uploaded_file = st.file_uploader("Upload Data (.csv or .xlsx)", type=["csv", "xlsx"])
    template_choice = st.selectbox("Select Avery Template", list(TEMPLATES.keys()))

if uploaded_file:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
            
        columns = ["--- Leave Blank ---"] + list(df.columns)
        
        with top_col1:
            st.write("**Select columns to print on each label:**")
            m_col1, m_col2 = st.columns(2)
            with m_col1:
                line1 = st.selectbox("Line 1", columns, index=0)
                line2 = st.selectbox("Line 2", columns, index=0)
                line3 = st.selectbox("Line 3", columns, index=0)
            with m_col2:
                line4 = st.selectbox("Line 4", columns, index=0)
                line5 = st.selectbox("Line 5", columns, index=0)
                line6 = st.selectbox("Line 6", columns, index=0)

        # --- NEW: LIVE PREVIEW & STYLING SECTION ---
        with top_col2:
            st.subheader("2. Styling & Live Preview")
            
            s_col1, s_col2 = st.columns(2)
            with s_col1:
                text_align = st.radio("Alignment", ["Left", "Center", "Right"], horizontal=True)
                text_style = st.radio("Style", ["Normal", "Bold", "Italic"], horizontal=True)
            with s_col2:
                font_size = st.slider("Font Size", min_value=6, max_value=24, value=10)
            
            # Generate the preview data using the VERY FIRST row of the uploaded sheet
            preview_lines = []
            for line_col in [line1, line2, line3, line4, line5, line6]:
                if line_col != "--- Leave Blank ---":
                    val = str(df.iloc[0].get(line_col, "")).strip()
                    if val and val.lower() != 'nan':
                        preview_lines.append(val)
            
            if not preview_lines:
                preview_lines = ["Map a column on the left", "to see your live preview here."]

            # CSS mapping for the web preview
            align_css = text_align.lower()
            weight_css = "bold" if text_style == "Bold" else "normal"
            font_style_css = "italic" if text_style == "Italic" else "normal"
            
            st.write("**Label Mockup:**")
            st.markdown(f"""
                <div class="preview-box" style="text-align: {align_css}; font-weight: {weight_css}; font-style: {font_style_css}; font-size: {font_size + 4}px; font-family: Arial, sans-serif;">
                    {'<br>'.join(preview_lines)}
                </div>
            """, unsafe_allow_html=True)
            
            st.write(" ")
            # Generate Button
            if st.button("Generate Print-Ready Labels", use_container_width=True):
                if all(line == "--- Leave Blank ---" for line in [line1, line2, line3, line4, line5, line6]):
                    st.warning("Please map at least one column to print.")
                else:
                    with st.spinner("Generating perfect PDF..."):
                        specs = TEMPLATES[template_choice]
                        pdf = FPDF(unit='mm', format='A4')
                        pdf.set_auto_page_break(auto=False)
                        pdf.add_page()
                        
                        # Apply chosen styles to the PDF generator
                        pdf_style = ""
                        if text_style == "Bold": pdf_style = "B"
                        elif text_style == "Italic": pdf_style = "I"
                        
                        pdf_align = "L"
                        if text_align == "Center": pdf_align = "C"
                        elif text_align == "Right": pdf_align = "R"
                        
                        pdf.set_font("Arial", style=pdf_style, size=font_size)

                        col_idx = 0
                        row_idx = 0

                        for index, row in df.iterrows():
                            x = specs["margin_left"] + (col_idx * specs["pitch_x"])
                            y = specs["margin_top"] + (row_idx * specs["pitch_y"])

                            lines_to_print = []
                            for line_col in [line1, line2, line3, line4, line5, line6]:
                                if line_col != "--- Leave Blank ---":
                                    val = str(row.get(line_col, "")).strip()
                                    if val and val.lower() != 'nan':
                                        lines_to_print.append(val)

                            padding_top = 5 if specs["label_height"] < 60 else 15
                            text_y = y + padding_top 
                            
                            for text in lines_to_print:
                                pdf.set_xy(x + 5, text_y)
                                # Using FPDF's cell width alignment correctly
                                pdf.cell(specs["label_width"] - 10, 4, txt=text, ln=0, align=pdf_align)
                                text_y += (font_size * 0.45) # Dynamically space lines based on font size

                            col_idx += 1
                            if col_idx >= specs["cols"]:
                                col_idx = 0
                                row_idx += 1

                            if row_idx >= specs["rows"]:
                                pdf.add_page()
                                col_idx = 0
                                row_idx = 0

                        # --- THE BUG FIX ---
                        pdf_out = pdf.output(dest='S')
                        # Check if the output is a string (older FPDF) or already bytes (modern FPDF2)
                        if isinstance(pdf_out, str):
                            pdf_bytes = pdf_out.encode('latin-1')
                        else:
                            pdf_bytes = bytes(pdf_out)
                        
                        st.success(f"✅ Generated {len(df)} styled labels perfectly mapped for {template_choice.split('|')[0].strip()}!")
                        st.download_button(
                            label="⬇️ Download Labels (PDF)",
                            data=pdf_bytes,
                            file_name=f"KEP_Labels_{template_choice.split(' ')[0]}.pdf",
                            mime="application/pdf"
                        )
                        
    except Exception as e:
        st.error(f"Error reading file: {e}")
else:
    st.info("Upload a spreadsheet on the left to begin mapping your label data.")
