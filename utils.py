"""
Shared helpers for the KEP Print Group internal portal.

This centralises a few things that used to be copy-pasted across
multiple pages (branding colours, the base64 image encoder), plus two
small additions:

- require_login(): an OFF-BY-DEFAULT password gate. If you haven't set
  an `app_password` secret, this does nothing and every page behaves
  exactly as before. See README.md > "Adding a login" to turn it on.

- locked_save(): wraps a save_*(df) call in a file lock so two people
  clicking "save" on the same CSV at the same moment can't corrupt the
  file or silently clobber each other's row. This does NOT solve data
  persisting across redeploys/restarts on hosts with an ephemeral
  filesystem (e.g. Streamlit Community Cloud) - see README.md for that.
"""
import base64
import os

import streamlit as st
from filelock import FileLock, Timeout

KEP_BLUE = "#004B87"

# --- Client / account branding, used by Tracking Consolidator & Carbon Impact Engine ---
BRANDING = {
    "F181494": {
        "name": "PrintFlo",
        "title": "PrintFlo Dispatch Report",
        "primary_color": "#005EB8",
        "header_bg": "#ffffff",
        "header_text": "#333333",
        "link": "https://printflo.co.uk/",
        "logo_text": "PrintFlo Fulfillment",
        "logo_file": "printflo-logo.png",
    },
    "F199630": {
        "name": "Mamas_and_Papas",
        "title": "Mamas & Papas Dispatch Report",
        "primary_color": "#000000",
        "header_bg": "#000000",
        "header_text": "#ffffff",
        "link": "https://www.mamasandpapas.com/",
        "logo_text": "M&P Campaign Dispatch",
        "logo_file": None,
    },
    "F090402": {
        "name": "KEP_Print_Group",
        "title": "KEP Dispatch Report",
        "primary_color": KEP_BLUE,
        "header_bg": KEP_BLUE,
        "header_text": "#ffffff",
        "link": "https://www.kep.co.uk/",
        "logo_text": "KEP Print Group",
        "logo_file": "logo.svg",
    },
}

DEFAULT_BRAND = {
    "name": "General_Dispatch",
    "title": "Dispatch Report",
    "primary_color": "#555555",
    "header_bg": "#555555",
    "header_text": "#ffffff",
    "link": "#",
    "logo_text": "Dispatch Tracking",
    "logo_file": None,
}


@st.cache_data(show_spinner=False)
def get_base64_image(filepath):
    """Base64-encode a local image/svg so it can be embedded in generated HTML."""
    if filepath and os.path.exists(filepath):
        with open(filepath, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
        ext = filepath.split(".")[-1].lower()
        mime = "image/svg+xml" if ext == "svg" else f"image/{ext}"
        return f"data:{mime};base64,{encoded}"
    return None


def require_login():
    """
    Optional shared-password gate for the whole app.

    Not configured -> no-op, app works exactly as it does today.
    Configured -> shows a password screen once per browser session.

    To turn this on, add to .streamlit/secrets.toml:
        app_password = "something-only-your-team-knows"
    """
    if "app_password" not in st.secrets:
        return

    if st.session_state.get("kep_authed"):
        return

    st.title("🔒 KEP Portal")
    with st.form("login_form"):
        pwd = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in")
    if submitted:
        if pwd == st.secrets["app_password"]:
            st.session_state["kep_authed"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    st.stop()


def locked_save(path, save_fn, *args, timeout=10, **kwargs):
    """
    Call save_fn(*args, **kwargs) while holding a lock file next to `path`.

    Prevents two concurrent saves to the same CSV from interleaving and
    corrupting the file. If another save is already in progress, waits
    up to `timeout` seconds, then shows a friendly error instead of
    risking a corrupt write.
    """
    lock_path = f"{path}.lock"
    try:
        with FileLock(lock_path, timeout=timeout):
            save_fn(*args, **kwargs)
    except Timeout:
        st.error(
            "Someone else is saving to this board right now — "
            "please wait a few seconds and try again."
        )
