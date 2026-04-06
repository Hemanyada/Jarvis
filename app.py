import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from ai import ask_assistant
from utils import (
    compare_phones_specs,
    dedupe_best_per_platform,
    get_best_deal,
    search_phone_prices,
    tag_phone,
)

load_dotenv()

st.set_page_config(
    page_title="Jarvis",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Polished UI: typography, tabs, cards ---
st.markdown(
    """
    <style>
    /* Tab bar: clearer grouping */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        padding: 6px 8px;
        border-radius: 12px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 10px !important;
        padding: 0.5rem 1rem !important;
        font-weight: 600 !important;
    }
    section[data-testid="stSidebar"] .block-container {
        padding-top: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _search_context_for_ai() -> str | None:
    if "last_search_results" not in st.session_state:
        return None
    results = st.session_state["last_search_results"]
    query = st.session_state.get("last_search_query", "")
    if not results:
        return None
    lines = [f"Current search: {query}"]
    for r in results:
        lines.append(f"  {r['platform']}: ₹{r['price']:,} — {r.get('url', '')}")
    return "\n".join(lines)


def render_ai_assistant(*, fullscreen: bool) -> None:
    """Single chat UI used in sidebar (compact) or main (fullscreen)."""
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    height = 620 if fullscreen else 420
    chat_box = st.container(height=height, border=True)

    with chat_box:
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    user_question = st.chat_input(
        "Ask about phones…",
        key="chat_input_fullscreen" if fullscreen else "chat_input_sidebar",
    )

    if not user_question:
        return

    st.session_state.chat_history.append({"role": "user", "content": user_question})

    with chat_box:
        with st.chat_message("user"):
            st.markdown(user_question)
        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                try:
                    search_ctx = _search_context_for_ai()
                    reply = ask_assistant(user_question, search_context=search_ctx)
                except Exception as e:
                    reply = f"Something went wrong: {e}"
            st.markdown(reply)

    st.session_state.chat_history.append({"role": "assistant", "content": reply})


# ---- API key checks ----
missing_keys = []
if not os.getenv("EXA_API_KEY"):
    missing_keys.append("EXA_API_KEY")
if not os.getenv("GEMINI_API_KEY"):
    missing_keys.append("GEMINI_API_KEY")

if "ai_fullscreen" not in st.session_state:
    st.session_state.ai_fullscreen = False

# ============================================================================
# Fullscreen AI: main area is only the assistant; minimal sidebar
# ============================================================================
if st.session_state.ai_fullscreen:
    with st.sidebar:
        if st.button("← Back to Jarvis", use_container_width=True, type="secondary"):
            st.session_state.ai_fullscreen = False
            st.rerun()

    with st.container(border=True):
        st.header("AI assistant (fullscreen)")
        st.caption("Ask about phones and deals. Your last price search is included as context when available.")
    render_ai_assistant(fullscreen=True)
    st.stop()

# ============================================================================
# Default layout: hero + tabs; assistant in sidebar
# ============================================================================
with st.container(border=True):
    st.title("Jarvis")
    st.markdown(
        "Your personal phone price comparison assistant — **search** prices, **compare** specs, and chat with **AI**."
    )

if missing_keys:
    with st.expander("Configuration", expanded=False):
        st.warning(
            f"Missing API keys: **{', '.join(missing_keys)}**. Add them to your `.env` file."
        )

tab_search, tab_compare = st.tabs(["Search", "Compare"])

with tab_search:
    st.markdown("##### Find the best price across Indian stores")
    with st.container(border=True):
        c1, c2 = st.columns([4, 1], vertical_alignment="bottom")
        with c1:
            search_query = st.text_input(
                "Phone name",
                placeholder="e.g. iPhone 15, Samsung Galaxy S23 Ultra, Motorola Edge 70 Fusion",
                key="search_query",
                label_visibility="collapsed",
            )
        with c2:
            search_btn = st.button("Search prices", use_container_width=True, type="primary")

    if search_btn and search_query:
        try:
            with st.spinner(f"Searching for **{search_query}** — this may take a few seconds…"):
                offers, out_of_stock = search_phone_prices(search_query)
                deduped = dedupe_best_per_platform(offers)

                st.session_state["last_search_results"] = deduped
                st.session_state["last_search_query"] = search_query

            if not deduped and not out_of_stock:
                st.info(
                    "No prices found. Try a more specific phone name (e.g. **Samsung Galaxy S24 Ultra**)."
                )
            else:
                    best = get_best_deal(deduped)

                    if best:
                        st.metric(
                            label=f"Best deal — {best['platform']}",
                            value=f"₹{best['price']:,}",
                            help="Lowest price found across searched platforms.",
                        )
                        st.caption("Open the **Buy link** in the table below to view offers.")

                    col_table, col_chart = st.columns(2, gap="large")

                    with col_table:
                        st.subheader("Price comparison")
                        rows = []
                        for o in deduped:
                            rows.append(
                                {
                                    "Platform": o["platform"],
                                    "Price": f"₹{o['price']:,}",
                                    "NumericPrice": o["price"],
                                    "Buy Link": o["url"],
                                    "Deal": "Best" if o is best else "",
                                }
                            )

                        for platform in out_of_stock:
                            rows.append(
                                {
                                    "Platform": platform,
                                    "Price": "Out of stock",
                                    "NumericPrice": None,
                                    "Buy Link": "",
                                    "Deal": "",
                                }
                            )

                        df = pd.DataFrame(rows)
                        priced = df[df["NumericPrice"].notna()].sort_values("NumericPrice")
                        oos = df[df["NumericPrice"].isna()]
                        df = pd.concat([priced, oos], ignore_index=True)

                        st.dataframe(
                            df[["Platform", "Price", "Deal", "Buy Link"]],
                            column_config={
                                "Buy Link": st.column_config.LinkColumn("Buy link"),
                            },
                            hide_index=True,
                            use_container_width=True,
                        )

                    with col_chart:
                        chart_rows = df[df["NumericPrice"].notna()]
                        if not chart_rows.empty:
                            st.subheader("Price chart")
                            chart_df = chart_rows[["Platform", "NumericPrice"]].set_index("Platform")
                            st.bar_chart(chart_df, y="NumericPrice")

                    st.divider()
                    st.subheader("Specifications")
                    with st.spinner("Fetching specifications (Exa + Gemini)…"):
                        try:
                            specs_list = compare_phones_specs([search_query])
                        except Exception as spec_err:
                            specs_list = []
                            st.warning(f"Could not load specifications: {spec_err}")

                    if specs_list:
                        for spec in specs_list:
                            spec["Tag"] = tag_phone(spec, spec["Name"])
                        specs_df = pd.DataFrame(specs_list)
                        spec_cols = ["Name", "Tag", "Display", "Processor", "Camera", "Battery"]
                        specs_df = specs_df[spec_cols]
                        st.dataframe(
                            specs_df.set_index("Name").T,
                            use_container_width=True,
                        )

        except Exception as e:
            st.error(f"Search error: {e}")

with tab_compare:
    st.markdown("##### Side‑by‑side specs (Exa + Gemini, same stores as price search)")
    with st.container(border=True):
        c1, c2 = st.columns([4, 1], vertical_alignment="bottom")
        with c1:
            compare_input = st.text_input(
                "Phones (comma‑separated)",
                placeholder="e.g. iPhone 15, S24 Ultra, Pixel 8",
                key="compare_input",
                label_visibility="collapsed",
            )
        with c2:
            compare_btn = st.button("Compare specs", use_container_width=True, type="primary")

    if compare_btn and compare_input:
        phone_names = [p.strip() for p in compare_input.split(",") if p.strip()]
        if len(phone_names) < 2:
            st.warning("Enter at least two phones to compare.")
        else:
            with st.spinner(
                "Fetching specs from Exa and extracting with Gemini — this may take a minute for multiple phones…"
            ):
                try:
                    specs_list = compare_phones_specs(phone_names)
                except Exception as e:
                    st.error(f"Compare failed: {e}")
                    specs_list = []

            if specs_list:
                for spec in specs_list:
                    spec["Tag"] = tag_phone(spec, spec["Name"])

                specs_df = pd.DataFrame(specs_list)
                cols = ["Name", "Tag", "Display", "Processor", "Camera", "Battery"]
                specs_df = specs_df[cols]

                st.subheader("Specifications")
                st.dataframe(specs_df.set_index("Name").T, use_container_width=True)

# ---- Sidebar: AI assistant (compact) + fullscreen ----
with st.sidebar:
    st.header("AI assistant")
    st.caption('Examples: “Best phone under ₹30,000”, “Best camera phone”, “Is this a good deal?”')
    if st.button("Fullscreen assistant", use_container_width=True, type="primary"):
        st.session_state.ai_fullscreen = True
        st.rerun()

    render_ai_assistant(fullscreen=False)