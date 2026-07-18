import streamlit as st

st.set_page_config(page_title="KEP Portal Home", page_icon="🏠", layout="wide")

st.title("Welcome to the KEP CSR Portal")
st.write("Use the sidebar on the left to navigate between different production tools.")
st.divider()

col1, col2, col3 = st.columns(3)

with col1:
    st.info("📦 **Pick Lists & Dispatch**\n\nGenerate PDFs and DHL CSVs for M&P, Tim Hortons, and Craft Union.")
with col2:
    st.warning("⚙️ **Collation Machine Prep**\n\nFormat raw mailing lists for the print room. *(Mockup)*")
with col3:
    st.success("📊 **Stock & Inventory**\n\nReview low stock and generate Tropicana POs. *(Mockup)*")
