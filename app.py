import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import pydeck as pdk
import spacy
import joblib
import re
import subprocess
import sys
from sklearn.model_selection import train_test_split

# ─── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="EarthSense AI",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

html, body, [class*="css"], .stApp {
    font-family: 'Inter', sans-serif;
}

/* Hide Streamlit chrome */
#MainMenu, footer { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent; }
.block-container {
    padding-top: 0.5rem !important;
    padding-bottom: 5rem !important;
    max-width: 1100px !important;
}

/* ── Hero ───────────────────────────────────────────────────── */
.hero {
    background: linear-gradient(135deg, #0a1628 0%, #1a2d4a 50%, #0f3460 100%);
    border-radius: 16px;
    padding: 1.1rem 1.5rem;
    margin-bottom: 1.25rem;
    text-align: center;
    position: relative;
    overflow: hidden;
}
.hero::before {
    content: '';
    position: absolute;
    top: -30%;
    left: -20%;
    width: 140%;
    height: 160%;
    background: radial-gradient(ellipse at center, rgba(255,107,53,0.12) 0%, transparent 65%);
    pointer-events: none;
}
.hero::after {
    content: '';
    position: absolute;
    bottom: -10px;
    left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, #FF6B35, transparent);
}
.hero-title {
    color: #ffffff;
    font-size: clamp(1.2rem, 3vw, 1.6rem);
    font-weight: 800;
    margin: 0 0 0.15rem;
    letter-spacing: -0.3px;
    position: relative;
}
.hero-subtitle {
    color: rgba(255,255,255,0.6);
    font-size: clamp(0.75rem, 2vw, 0.85rem);
    margin: 0 0 0.6rem;
    position: relative;
    font-weight: 400;
}
.hero-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    justify-content: center;
    position: relative;
}
.chip {
    background: rgba(255,255,255,0.1);
    border: 1px solid rgba(255,255,255,0.15);
    color: rgba(255,255,255,0.85);
    border-radius: 100px;
    padding: 0.15rem 0.6rem;
    font-size: 0.72rem;
    font-weight: 500;
    backdrop-filter: blur(4px);
}


/* ── Predict Button ─────────────────────────────────────────── */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #FF6B35 0%, #e85520 100%) !important;
    color: white !important;
    border: none !important;
    border-radius: 14px !important;
    font-size: 1rem !important;
    font-weight: 700 !important;
    padding: 0.7rem 1.5rem !important;
    letter-spacing: 0.2px;
    box-shadow: 0 4px 15px rgba(255,107,53,0.35) !important;
    transition: all 0.2s !important;
}
.stButton > button[kind="primary"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 22px rgba(255,107,53,0.45) !important;
}
.stButton > button[kind="secondary"] {
    border-radius: 12px !important;
    font-weight: 600 !important;
}

/* ── Result Banner ──────────────────────────────────────────── */
.result-banner {
    border-radius: 16px;
    padding: 1.2rem 1.5rem;
    text-align: center;
    margin: 1rem 0 0;
    font-weight: 700;
    font-size: 1.25rem;
    color: white;
    box-shadow: 0 6px 24px rgba(0,0,0,0.2);
}
.result-sub {
    font-size: 0.85rem;
    font-weight: 400;
    opacity: 0.9;
    margin-top: 0.2rem;
}

/* ── Severity Pills ─────────────────────────────────────────── */
.sev-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    border-radius: 100px;
    padding: 0.25rem 0.9rem;
    font-size: 0.8rem;
    font-weight: 700;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}

/* ── Floating Chat FAB ──────────────────────────────────────── */
.chat-fab-wrap {
    position: fixed;
    bottom: 2rem;
    right: 2rem;
    z-index: 10000;
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 0.5rem;
}
.chat-fab {
    width: 62px;
    height: 62px;
    background: linear-gradient(135deg, #FF6B35 0%, #e85520 100%);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    font-size: 28px;
    box-shadow: 0 4px 20px rgba(255,107,53,0.5), 0 2px 8px rgba(0,0,0,0.15);
    text-decoration: none;
    transition: transform 0.2s, box-shadow 0.2s;
    border: 2px solid rgba(255,255,255,0.3);
}
.chat-fab:hover {
    transform: scale(1.1) rotate(-5deg);
    box-shadow: 0 8px 28px rgba(255,107,53,0.6);
}
.chat-fab-tooltip {
    background: #0a1628;
    color: white;
    font-size: 0.75rem;
    font-weight: 600;
    padding: 0.3rem 0.7rem;
    border-radius: 8px;
    white-space: nowrap;
    opacity: 0;
    transition: opacity 0.2s;
    pointer-events: none;
}
.chat-fab-wrap:hover .chat-fab-tooltip { opacity: 1; }

/* ── Chat Panel ─────────────────────────────────────────────── */
.chat-panel-header {
    background: linear-gradient(135deg, #0a1628, #1a2d4a);
    border-radius: 18px 18px 0 0;
    padding: 1rem 1.5rem;
    display: flex;
    align-items: center;
    gap: 0.75rem;
}
.chat-avatar {
    width: 40px;
    height: 40px;
    background: linear-gradient(135deg, #FF6B35, #e85520);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    flex-shrink: 0;
}
.chat-panel-title { color: white; font-weight: 700; font-size: 1rem; margin: 0; }
.chat-panel-sub { color: rgba(255,255,255,0.6); font-size: 0.78rem; margin: 0; }
.chat-online {
    width: 8px; height: 8px;
    background: #2ecc71;
    border-radius: 50%;
    margin-left: auto;
    box-shadow: 0 0 6px #2ecc71;
}
.chat-divider {
    border: none;
    border-top: 1px solid rgba(0,0,0,0.08);
    margin: 0;
}

/* ── Input Overrides ────────────────────────────────────────── */
.stNumberInput > div > div > input {
    border-radius: 12px !important;
    border: 2px solid #e8edf2 !important;
    font-size: 1rem !important;
    transition: border-color 0.2s !important;
}
.stNumberInput > div > div > input:focus {
    border-color: #FF6B35 !important;
    box-shadow: 0 0 0 3px rgba(255,107,53,0.12) !important;
}

/* ── Tabs ───────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    gap: 0.5rem;
    background: transparent;
    border-bottom: 2px solid #e8edf2;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 10px 10px 0 0 !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    padding: 0.5rem 1.2rem !important;
    color: #8895a7 !important;
}
.stTabs [aria-selected="true"] {
    color: #FF6B35 !important;
    background: rgba(255,107,53,0.08) !important;
}

/* ── Expander ───────────────────────────────────────────────── */
.stExpander {
    border: 1px solid #e8edf2 !important;
    border-radius: 16px !important;
    overflow: hidden !important;
}

/* ── Mobile ─────────────────────────────────────────────────── */
@media (max-width: 640px) {
    .block-container { padding: 0.25rem 0.75rem 5rem !important; }
    .hero { padding: 0.75rem 1rem; border-radius: 12px; }
    .chat-fab-wrap { bottom: 1.25rem; right: 1.25rem; }
    .chat-fab { width: 54px; height: 54px; font-size: 24px; }
    .result-banner { font-size: 1.1rem; }
}
</style>
""", unsafe_allow_html=True)

# ─── Session State ─────────────────────────────────────────────────────────────
if 'chat_open' not in st.session_state:
    st.session_state.chat_open = False
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'last_prediction' not in st.session_state:
    st.session_state.last_prediction = None

# ─── Load Models & Data ────────────────────────────────────────────────────────
@st.cache_resource(show_spinner="Loading prediction model...")
def load_model():
    try:
        return joblib.load("earthquake_magnitude_model_compatible.pkl")
    except Exception:
        return joblib.load("data/earthquake_magnitude_model.pkl")

@st.cache_resource(show_spinner="Loading NLP engine...")
def load_nlp():
    try:
        return spacy.load("en_core_web_sm")
    except OSError:
        subprocess.check_call([sys.executable, "-m", "spacy", "download", "en_core_web_sm"])
        return spacy.load("en_core_web_sm")

@st.cache_data(show_spinner="Loading earthquake database...")
def load_data():
    df = pd.read_excel(
        "data/Official Website of National Center of Seismology.xlsx",
        sheet_name="Sheet1",
    )
    df_cleaned = df[1:].copy()
    df_cleaned.columns = df.iloc[0]
    df_cleaned = df_cleaned[1:]
    for col in ["Lat", "Long", "Magnitude", "Depth"]:
        df_cleaned[col] = pd.to_numeric(df_cleaned[col], errors="coerce")
    df_cleaned["Region"] = df_cleaned["Region"].astype(str)
    return df_cleaned.dropna(subset=["Lat", "Long", "Magnitude", "Depth"])

model = load_model()
df = load_data()

# ─── Helper ────────────────────────────────────────────────────────────────────
def mag_severity(m):
    if m < 2.0:   return "🟢", "Micro",    "#27AE60", "#e8f8f0"
    if m < 4.0:   return "🟡", "Minor",    "#F39C12", "#fdf6e3"
    if m < 5.0:   return "🟠", "Moderate", "#E67E22", "#fef0e6"
    if m < 6.0:   return "🔴", "Strong",   "#C0392B", "#fde8e8"
    if m < 7.0:   return "🚨", "Major",    "#8E44AD", "#f5eafd"
    return         "⚫", "Great",   "#2C3E50", "#eaebec"

# ─── Hero Banner ───────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
    <div class="hero-title">🌍 EarthSense AI</div>
    <div class="hero-subtitle">Earthquake magnitude prediction & intelligence platform</div>
    <div class="hero-chips">
        <span class="chip">📡 NCS India Dataset</span>
        <span class="chip">🤖 ML Powered</span>
        <span class="chip">💬 NLP Chatbot</span>
        <span class="chip">🗺️ Live Map</span>
    </div>
</div>
""", unsafe_allow_html=True)

# ─── Main Prediction Card ───────────────────────────────────────────────────────
st.subheader("🔮 Magnitude Predictor")
st.caption("Enter location coordinates and depth to predict earthquake magnitude")

col1, col2, col3 = st.columns(3)
with col1:
    lat = st.number_input("📍 Latitude", value=28.5, min_value=-90.0, max_value=90.0, format="%.4f", help="North (+) / South (−)")
with col2:
    lon = st.number_input("📍 Longitude", value=77.2, min_value=-180.0, max_value=180.0, format="%.4f", help="East (+) / West (−)")
with col3:
    depth = st.number_input("⬇️ Depth (km)", value=10.0, min_value=0.0, max_value=700.0, format="%.1f", help="Hypocentral depth")

predict_col, chat_col = st.columns([3, 1])
with predict_col:
    predict_btn = st.button("🌋 Predict Magnitude", type="primary", use_container_width=True)
with chat_col:
    if st.button("💬 Ask AI", use_container_width=True, help="Open the earthquake chatbot"):
        st.session_state.chat_open = True
        st.rerun()

if predict_btn:
    input_data = pd.DataFrame({"Lat": [lat], "Long": [lon], "Depth": [depth]})
    prediction = model.predict(input_data)[0]
    st.session_state.last_prediction = {"mag": prediction, "lat": lat, "lon": lon, "depth": depth}

if st.session_state.last_prediction:
    p = st.session_state.last_prediction
    icon, label, color, bg = mag_severity(p["mag"])
    st.markdown(f"""
    <div class="result-banner" style="background: linear-gradient(135deg, {color}dd, {color});">
        <div>{icon} Predicted Magnitude: <span style="font-size:1.5rem;">{p["mag"]:.2f}</span></div>
        <div class="result-sub">{label} — Lat {p["lat"]:.3f}°, Lon {p["lon"]:.3f}°, Depth {p["depth"]:.0f} km</div>
    </div>
    """, unsafe_allow_html=True)

# ─── Model Performance Chart ───────────────────────────────────────────────────
with st.expander("📊 Model Performance — Predicted vs Actual", expanded=False):
    X = df[["Lat", "Long", "Depth"]]
    y = df["Magnitude"]
    _, X_test, _, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    y_pred_all = model.predict(X_test)

    fig, ax = plt.subplots(figsize=(9, 4))
    fig.patch.set_facecolor("#0a1628")
    ax.set_facecolor("#111e30")
    sc = ax.scatter(y_test, y_pred_all, alpha=0.55, c=y_pred_all, cmap="plasma", s=18, linewidths=0)
    ax.plot([y_test.min(), y_test.max()], [y_test.min(), y_test.max()],
            color="#FF6B35", linestyle="--", linewidth=1.5, alpha=0.8, label="Perfect prediction")
    plt.colorbar(sc, ax=ax, label="Predicted Magnitude").ax.yaxis.label.set_color("white")
    ax.set_xlabel("Actual Magnitude", color="#a8b4c0", fontsize=10)
    ax.set_ylabel("Predicted Magnitude", color="#a8b4c0", fontsize=10)
    ax.set_title("Predicted vs Actual Magnitudes (Test Set)", color="white", fontsize=12, fontweight="bold", pad=12)
    ax.tick_params(colors="#a8b4c0", labelsize=9)
    for spine in ax.spines.values():
        spine.set_color("#1e3050")
    ax.grid(True, alpha=0.12, color="#4a6080")
    ax.legend(facecolor="#0a1628", labelcolor="white", framealpha=0.9, fontsize=9)
    fig.tight_layout()
    st.pyplot(fig, use_container_width=True)

# ─── Chat Panel ─────────────────────────────────────────────────────────────────
if st.session_state.chat_open:
    st.markdown("<br>", unsafe_allow_html=True)

    # Header
    st.markdown("""
    <div class="chat-panel-header">
        <div class="chat-avatar">🤖</div>
        <div>
            <div class="chat-panel-title">Earthquake AI Assistant</div>
            <div class="chat-panel-sub">Ask about regions, recent quakes, or get predictions</div>
        </div>
        <div class="chat-online"></div>
    </div>
    <hr class="chat-divider">
    """, unsafe_allow_html=True)

    # Suggestion pills
    if not st.session_state.messages:
        st.markdown("**Try asking:**", help=None)
        sug_cols = st.columns(3)
        sug_map = {
            "Recent in Japan \U0001f5fe": "Recent in Japan",
            "Predict 28.5, 77.2, 10 \U0001f52e": "Predict 28.5, 77.2, 10",
            "Earthquakes in Himachal \U0001f3d4️": "Earthquakes in Himachal",
        }
        for i, (label, query) in enumerate(sug_map.items()):
            with sug_cols[i]:
                if st.button(label, key=f"sug_{i}", use_container_width=True):
                    st.session_state._pending_input = query
                    st.rerun()

    # Handle suggestion click
    if hasattr(st.session_state, "_pending_input") and st.session_state._pending_input:
        pending = st.session_state._pending_input
        st.session_state._pending_input = None
        user_query = pending
    else:
        user_query = None

    def render_region_results(top_records, map_records, center_lat, center_lon):
        """Re-usable renderer for the table + map so history replay looks identical."""
        top = pd.DataFrame(top_records)
        st.dataframe(top, use_container_width=True, hide_index=True)
        st.markdown("**📍 Earthquake Map**")
        map_data = pd.DataFrame(map_records)
        map_data["radius"] = (map_data["Magnitude"] ** 2) * 8000
        st.pydeck_chart(pdk.Deck(
            map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
            initial_view_state=pdk.ViewState(
                latitude=center_lat, longitude=center_lon, zoom=4, pitch=35,
            ),
            layers=[pdk.Layer(
                "ScatterplotLayer",
                data=map_data,
                get_position="[Long, Lat]",
                get_fill_color="[255, 107, 53, 180]",
                get_radius="radius",
                pickable=True,
            )],
            tooltip={"text": "Magnitude: {Magnitude}"},
        ))

    # Chat history
    for msg in st.session_state.messages:
        avatar = "🤖" if msg["role"] == "assistant" else "👤"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])
            if msg.get("region_top"):
                render_region_results(
                    msg["region_top"], msg["region_map"],
                    msg["center_lat"], msg["center_lon"],
                )

    # Chat input
    user_input = st.chat_input("Ask about earthquakes (region name or 'predict lat, lon, depth')…")
    if user_input:
        user_query = user_input

    # Process query
    if user_query:
        st.session_state.messages.append({"role": "user", "content": user_query})
        response = ""  # always defined

        extra = {}  # extra data to store alongside message text

        with st.chat_message("assistant", avatar="🤖"):
            coords = re.findall(r"[-+]?\d*\.\d+|\d+", user_query.replace(",", " "))

            if len(coords) >= 3 and any(kw in user_query.lower() for kw in ["predict", "magnitude", "lat", "lon", str(coords[0])[:3]]):
                # ── Coordinate prediction ──────────────────────────────────────
                try:
                    p_lat, p_lon, p_depth = float(coords[0]), float(coords[1]), float(coords[2])
                    mag = model.predict(pd.DataFrame({"Lat": [p_lat], "Long": [p_lon], "Depth": [p_depth]}))[0]
                    icon, label, color, _ = mag_severity(mag)
                    response = (
                        f"**{icon} Predicted Magnitude: {mag:.2f}** ({label})\n\n"
                        f"📍 Lat **{p_lat}**, Lon **{p_lon}**, Depth **{p_depth} km**"
                    )
                except Exception as e:
                    response = f"⚠️ Prediction failed: {e}"
                st.markdown(response)

            else:
                # ── NLP region search ─────────────────────────────────────────
                try:
                    nlp_model = load_nlp()
                    doc = nlp_model(user_query)
                    locations = [ent.text for ent in doc.ents if ent.label_ in ("GPE", "LOC")]
                except Exception:
                    locations = []

                # Keyword fallback if NLP found nothing
                if not locations:
                    stopwords = {"predict", "recent", "earthquakes", "earthquake", "about", "show", "find", "list"}
                    locations = [w for w in re.findall(r'\b[A-Za-z]{4,}\b', user_query) if w.lower() not in stopwords]

                if locations:
                    region = locations[0]
                    result = df[df["Region"].str.contains(region, case=False, na=False)]

                    if not result.empty:
                        count = len(result)
                        avg_mag = result["Magnitude"].mean()
                        max_mag = result["Magnitude"].max()
                        center_lat = result["Lat"].mean()
                        center_lon = result["Long"].mean()
                        icon, label, _, _ = mag_severity(max_mag)

                        response = (
                            f"🔍 Found **{count} earthquakes** in **{region}**  \n"
                            f"Avg magnitude: **{avg_mag:.2f}** | Max: **{max_mag:.2f}** {icon} ({label})"
                        )
                        st.markdown(response)

                        top_df = result.head(5)[["Origin Time", "Lat", "Long", "Depth", "Magnitude", "Region"]].reset_index(drop=True)
                        map_df = result[["Lat", "Long", "Magnitude"]].copy()

                        render_region_results(
                            top_df.to_dict("records"),
                            map_df.to_dict("records"),
                            center_lat, center_lon,
                        )

                        # Store data so history replay can re-render table + map
                        extra = {
                            "region_top": top_df.to_dict("records"),
                            "region_map": map_df.to_dict("records"),
                            "center_lat": center_lat,
                            "center_lon": center_lon,
                        }
                    else:
                        response = f"No earthquakes found for **{region}** in the database."
                        st.markdown(response)
                        extra = {}
                else:
                    response = (
                        "❓ I couldn't parse that query. Try:\n\n"
                        "- **Region search:** *'Recent in Japan'*, *'Earthquakes in Gujarat'*\n"
                        "- **Prediction:** *'Predict 28.5, 77.2, 10'*"
                    )
                    st.markdown(response)

        st.session_state.messages.append({"role": "assistant", "content": response, **extra})
        st.rerun()

    # Close button
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("✕ Close Chat", use_container_width=False):
        st.session_state.chat_open = False
        st.session_state.messages = []
        st.rerun()

# ─── Floating Chat FAB ─────────────────────────────────────────────────────────
if not st.session_state.chat_open:
    st.markdown("""
    <div class="chat-fab-wrap">
        <div class="chat-fab-tooltip">AI Chatbot</div>
    </div>
    """, unsafe_allow_html=True)

    # Real clickable FAB via Streamlit button with CSS override
    st.markdown("""
    <style>
    div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] > div > div[data-testid="stButton"].fab-btn) {
        position: fixed;
        bottom: 2rem;
        right: 2rem;
        z-index: 10000;
    }
    .fab-btn > div > button {
        width: 62px !important;
        height: 62px !important;
        border-radius: 50% !important;
        background: linear-gradient(135deg, #FF6B35 0%, #e85520 100%) !important;
        color: white !important;
        font-size: 26px !important;
        border: 2px solid rgba(255,255,255,0.3) !important;
        box-shadow: 0 4px 20px rgba(255,107,53,0.55) !important;
        padding: 0 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        cursor: pointer !important;
        transition: transform 0.2s, box-shadow 0.2s !important;
    }
    .fab-btn > div > button:hover {
        transform: scale(1.12) !important;
        box-shadow: 0 8px 28px rgba(255,107,53,0.65) !important;
    }
    </style>
    """, unsafe_allow_html=True)

    _, _, fab_col = st.columns([10, 1, 1])
    with fab_col:
        st.markdown('<div class="fab-btn">', unsafe_allow_html=True)
        if st.button("💬", key="fab_open", help="Open AI Chatbot"):
            st.session_state.chat_open = True
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
