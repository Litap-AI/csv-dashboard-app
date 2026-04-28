import streamlit as st
import base64
import tempfile
import os

from archival_dashboard_generator import parse_survey_csv, analyse, build_html

# OpenAI (new SDK style)
from openai import OpenAI

st.set_page_config(layout="wide")

# ---------- BACKGROUND ---------- #
def set_bg():
    current_dir = os.path.dirname(__file__)
    image_path = os.path.join(current_dir, "bg.png")

    with open(image_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode()

    st.markdown(f"""
    <style>
    header, footer {{visibility: hidden;}}
    [data-testid="stToolbar"],
    [data-testid="stHeader"],
    [data-testid="stDecoration"] {{
        display: none;
    }}

    .stApp {{
        background-image: url("data:image/png;base64,{encoded}");
        background-size: cover;
        background-position: center;
    }}

    .block-container {{
        max-width: 450px;
        margin: auto;
        margin-top: 120px;
        padding: 40px;
        border-radius: 20px;
        background: rgba(255,255,255,0.08);
        backdrop-filter: blur(18px);
        box-shadow: 0 0 40px rgba(0,0,0,0.5);
        text-align: center;
    }}

    h1 {{color: white !important;}}
    p {{color: #ddd !important;}}

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

# ---------- AI FUNCTION ---------- #
def generate_ai_insight(data):
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        return "⚠️ No API key found. Set OPENAI_API_KEY to enable AI insights."

    client = OpenAI(api_key=api_key)

    prompt = f"""
    Analyze this archival dataset summary and give clear insights:

    Total records: {data['total']}
    Condition A: {data['cond_a']}
    Condition B: {data['cond_b']}
    Condition C: {data['cond_c']}
    Avg pages: {data['avg_pages']}
    Damage: {data['damage']}

    Give 4-5 meaningful insights in simple bullet points.
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content


# ---------- MAIN ACTION ---------- #
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

            # Download
            st.download_button(
                "⬇ Download Dashboard",
                data=html,
                file_name="dashboard.html",
                mime="text/html"
            )

            # AI Insights
            st.write("## 🤖 AI Insights")
            ai_text = generate_ai_insight(data)
            st.write(ai_text)

        else:
            st.error("Invalid CSV")

    else:
        st.warning("Upload file first")
        
