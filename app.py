import streamlit as st
import base64
import tempfile
import os

from archival_dashboard_generator import parse_survey_csv, analyse, build_html

st.set_page_config(layout="wide")


# ---------- BACKGROUND ---------- #
def set_bg():
    current_dir = os.path.dirname(__file__)
    image_path = os.path.join(current_dir, "bg.png")

    with open(image_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode()

    st.markdown(f"""
    <style>

    /* Remove default UI */
    header, footer {{visibility: hidden;}}
    [data-testid="stToolbar"],
    [data-testid="stHeader"],
    [data-testid="stDecoration"] {{
        display: none;
    }}

    /* Background */
    .stApp {{
        background-image: url("data:image/png;base64,{encoded}");
        background-size: cover;
        background-position: center;
    }}

    /* Center everything */
    .main {{
        display: flex;
        justify-content: center;
        align-items: center;
        height: 100vh;
    }}

    /* Glass container */
    .block-container {{
        max-width: 450px;
        margin: auto;
        margin-top: 120px;
        padding: 40px;
        border-radius: 20px;
        background: rgba(255,255,255,0.08);
        backdrop-filter: blur(18px);
        -webkit-backdrop-filter: blur(18px);
        box-shadow: 0 0 40px rgba(0,0,0,0.5);
        text-align: center;
    }}

    /* Title */
    h1 {{
        color: white !important;
        font-size: 34px;
        text-align: center;
    }}

    p {{
        color: #ddd !important;
        text-align: center;
    }}

    /* Upload box styling */
    [data-testid="stFileUploader"] {{
        background: rgba(255,255,255,0.1);
        padding: 10px;
        border-radius: 10px;
    }}

    /* Button styling */
    .stButton > button {{
        width: 100%;
        background: #4CAF50;
        color: white;
        border-radius: 10px;
        font-size: 16px;
    }}

    </style>
    """, unsafe_allow_html=True)


set_bg()

# ---------- UI ---------- #

st.title("CSV → Dashboard")
st.write("Upload CSV & click Generate")

uploaded_file = st.file_uploader("", type=["csv"], label_visibility="collapsed")

if st.button("Generate"):
    if uploaded_file:

        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
            tmp.write(uploaded_file.read())
            path = tmp.name

        records = parse_survey_csv(path)

        if records:
            data = analyse(records)
            html = build_html(data)

            st.success("Dashboard ready!")

            st.download_button(
                "⬇ Download Dashboard",
                data=html,
                file_name="dashboard.html",
                mime="text/html"
            )
        else:
            st.error("Invalid CSV")

    else:
        st.warning("Upload file first")
        