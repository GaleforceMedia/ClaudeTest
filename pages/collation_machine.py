import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Collation Machine", page_icon="⚙️", layout="wide")

# Ensure the iframe takes up the full available screen space
st.title("⚙️ Collation Machine Editor")

# Using Streamlit's built-in iframe component
components.iframe(
    "https://dmtaylor-apps.github.io/WorkApps/CollationMachineEditor.html",
    width=1400,
    height=800,
    scrolling=True
)
