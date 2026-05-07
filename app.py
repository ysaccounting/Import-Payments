import streamlit as st
import pandas as pd
import io
from datetime import date
from parsers import parse_file

st.set_page_config(page_title="CSV Import to TV", page_icon="🎟️", layout="centered")

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500&display=swap');
  html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
  .eyebrow {
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.12em;
    color: #888780;
    text-transform: uppercase;
    margin-bottom: 4px;
  }
  .title { font-size: 28px; font-weight: 300; letter-spacing: -0.02em; margin-bottom: 24px; }
  .title span { font-weight: 500; }
  .stat-box {
    background: #f5f4f0;
    border-radius: 10px;
    padding: 14px 16px;
    text-align: center;
  }
  .stat-label {
    font-size: 11px;
    color: #888780;
    font-weight: 500;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    margin-bottom: 4px;
  }
  .stat-val { font-size: 22px; font-weight: 500; color: #1a1a18; }
  button[kind="secondary"] {
    background-color: #e0e0e0 !important;
    color: #222 !important;
    border: 1px solid #bbb !important;
  }
  button[kind="secondary"]:hover {
    background-color: #c8c8c8 !important;
    border: 1px solid #999 !important;
  }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="eyebrow">Remittance converter</div>', unsafe_allow_html=True)
st.markdown('<div class="title"><strong>CSV Import to TicketVault</strong></div>', unsafe_allow_html=True)

# ── Reset handler ─────────────────────────────────────────────────────────────
def reset():
    st.session_state["reset_counter"] = st.session_state.get("reset_counter", 0) + 1

if "reset_counter" not in st.session_state:
    st.session_state["reset_counter"] = 0

rc = st.session_state["reset_counter"]

# ── Inputs ────────────────────────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)

with col1:
    company = st.selectbox("Company", ["", "YS", "TV"], index=0,
                           format_func=lambda x: "Select..." if x == "" else x,
                           key=f"company_{rc}")

with col2:
    network = st.selectbox("Network", [
        "", "Gametime", "GoTickets", "Mercury", "SeatGeek", "StubHub",
        "Ticket Evolution", "TicketNetwork", "TicketsNow", "TickPick", "Vivid"
    ], index=0, format_func=lambda x: "Select..." if x == "" else x,
    key=f"network_{rc}")

with col3:
    remit_date = st.date_input("Remittance date", value=None, format="MM/DD/YYYY", key=f"remit_date_{rc}")

# ── Ticket Evolution: date range filter ───────────────────────────────────────
date_start = None
date_end   = None
if network == "Ticket Evolution":
    st.markdown("**Transaction date range** — only transactions within this range will be included.")
    dc1, dc2 = st.columns(2)
    with dc1:
        date_start = st.date_input("Start date", value=None, format="MM/DD/YYYY", key=f"te_start_{rc}")
    with dc2:
        date_end = st.date_input("End date", value=None, format="MM/DD/YYYY", key=f"te_end_{rc}")

# ── File uploader ─────────────────────────────────────────────────────────────
multi = network in ("StubHub", "TicketsNow", "TicketNetwork", "Mercury")

uploaded_files = st.file_uploader(
    "Upload remittance file",
    type=["csv", "xlsx", "xls"],
    accept_multiple_files=multi,
    label_visibility="collapsed",
    help="Drop your remittance file(s) here (.csv or .xlsx)",
    key=f"uploader_{rc}"
)

if multi:
    if network == "StubHub":
        st.markdown("*StubHub: drop multiple files and they'll be combined automatically.*")
    elif network == "TicketsNow":
        st.markdown("*TicketsNow: drop multiple files and they'll be combined automatically.*")
    elif network == "TicketNetwork":
        st.markdown("*TicketNetwork: drop the Details file and the Adjustments file together.*")
    elif network == "Mercury":
        st.markdown("*Mercury: drop the Details file and the Adjustments file together.*")
else:
    st.markdown("*Drag & drop or click above to upload your remittance file (.csv or .xlsx)*")

# ── Clear / Reset button ──────────────────────────────────────────────────────
st.markdown("")
if st.button("Clear / Reset", key=f"reset_{rc}"):
    reset()
    st.rerun()

# Normalise to list
if isinstance(uploaded_files, list):
    files = uploaded_files
else:
    files = [uploaded_files] if uploaded_files else []

# ── Extra validation for Ticket Evolution ─────────────────────────────────────
te_ready = True
if network == "Ticket Evolution" and (not date_start or not date_end):
    te_ready = False
    if files:
        st.warning("Please select a Start date and End date for Ticket Evolution.")

# ── Validation & Parsing ──────────────────────────────────────────────────────
if files and company and network and remit_date and te_ready:
    with st.spinner(f"Parsing {len(files)} file(s)..."):
        try:
            frames = []
            for f in files:
                kwargs = {}
                if network == "Ticket Evolution":
                    kwargs["date_start"] = date_start
                    kwargs["date_end"]   = date_end
                result = parse_file(f, network, **kwargs)
                if result is not None and not result.empty:
                    frames.append(result)
            df = pd.concat(frames, ignore_index=True) if frames else None
        except Exception as e:
            st.error(f"Could not parse file: {e}")
            st.stop()

    if df is None or df.empty:
        st.error("Could not parse file — check that the file matches the selected network.")
        st.stop()

    if len(files) > 1:
        st.info(f"Combined {len(files)} files → {len(df):,} rows total.")

    # Add remittance date column, format as M/D/YYYY
    date_str = f"{remit_date.month}/{remit_date.day}/{remit_date.year}"
    df["remittancedate"] = date_str

    # Reorder columns and put chargebacks at the bottom
    df = df[["order#", "amount", "remittancedate", "chargebackreason"]]
    df = pd.concat([
        df[df["amount"] >= 0],
        df[df["amount"] <  0]
    ], ignore_index=True)

    # ── Stats ─────────────────────────────────────────────────────────────────
    gross          = df[df["amount"] > 0]["amount"].sum()
    net            = df["amount"].sum()
    chargeback_amt = df[df["amount"] < 0]["amount"].sum()

    st.markdown("---")
    s1, s2, s3, s4 = st.columns(4)
    with s1:
        st.markdown(f'<div class="stat-box"><div class="stat-label">Total rows</div><div class="stat-val">{len(df):,}</div></div>', unsafe_allow_html=True)
    with s2:
        st.markdown(f'<div class="stat-box"><div class="stat-label">Gross</div><div class="stat-val">${gross:,.2f}</div></div>', unsafe_allow_html=True)
    with s3:
        st.markdown(f'<div class="stat-box"><div class="stat-label">Chargebacks</div><div class="stat-val">${abs(chargeback_amt):,.2f}</div></div>', unsafe_allow_html=True)
    with s4:
        st.markdown(f'<div class="stat-box"><div class="stat-label">Net total</div><div class="stat-val">${net:,.2f}</div></div>', unsafe_allow_html=True)

    st.markdown("#### Preview — first 8 rows")
    st.dataframe(df.head(8), use_container_width=True, hide_index=True)

    # ── Download ──────────────────────────────────────────────────────────────
    csv_out    = df.to_csv(index=False)
    short_date = remit_date.strftime("%m-%d-%y")
    filename   = f"{company}_{network.replace(' ', '')}_{short_date}.csv"

    st.download_button(
        label="Download CSV",
        data=csv_out,
        file_name=filename,
        mime="text/csv",
        type="primary",
        use_container_width=False,
    )

elif files and (not company or not network or not remit_date):
    st.warning("Please select Company, Network, and Remittance Date before uploading.")
