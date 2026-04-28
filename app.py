import streamlit as st
import base64
import tempfile
import os

from archival_dashboard_generator import parse_survey_csv, analyse, build_html

# Gemini
import google.generativeai as genai

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


# ---------- GEMINI FUNCTION ---------- #
def generate_ai_insight(data):
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        return "⚠️ No Gemini API key found. Set GEMINI_API_KEY in Streamlit Secrets."

    genai.configure(api_key=api_key)

    model = genai.GenerativeModel("gemini-1.5-flash")

    prompt = f"""
    You are a data analyst.

    Analyze this archival dataset and give meaningful insights:

    Total records: {data['total']}
    Condition A: {data['cond_a']}
    Condition B: {data['cond_b']}
    Condition C: {data['cond_c']}
    Average pages: {data['avg_pages']}
    Damage breakdown: {data['damage']}

    Provide 4-5 sharp insights in bullet points.
    Avoid generic statements.
    """

    response = model.generate_content(prompt)

    return response.text


# ---------- MAIN ---------- #
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

            st.write("## 🤖 AI Insights")

            try:
                with st.spinner("Analyzing data..."):
                    ai_text = generate_ai_insight(data)
                    st.write(ai_text)

            except Exception:
                st.warning("AI unavailable. Showing basic insights.")

                st.write(f"• Total records: {data['total']}")
                st.write(f"• Condition C (poor): {data['cond_c']}")
                st.write(f"• Average pages: {data['avg_pages']}")

        else:
            st.error("Invalid CSV")

    else:
        st.warning("Upload file first")
        
