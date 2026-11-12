import time
from datetime import datetime
import pytz
import streamlit as st
import pandas as pd
import plotly.express as px
from fyers_apiv3 import fyersModel

st.set_page_config(page_title="NSE Sector Heatmap", page_icon="📊", layout="centered")

st.markdown("""
    <style>
        .block-container { padding-top: 1.2rem; padding-bottom: 1rem; padding-left: 0.8rem; padding-right: 0.8rem; }
        button[data-baseweb="tab"] { font-size: 14px; font-weight: 600; padding-left: 8px; padding-right: 8px; }
    </style>
""", unsafe_allow_html=True)

st.title("📊 NSE Live Sector Scanner")
st.caption("Intraday Momentum vs. 9:15 AM Open Price")

if "access_token" not in st.session_state:
    st.session_state.access_token = ""
if "client_id" not in st.session_state:
    st.session_state.client_id = ""

# --- COLLAPSIBLE LOGIN SECTION ---
with st.expander("🔑 Fyers API Login (Tap once every morning)", expanded=(st.session_state.access_token == "")):
    client_id_input = st.text_input("Fyers App ID (ends in -100)", value=st.session_state.client_id, placeholder="XC4XXXXM-100")
    secret_key_input = st.text_input("Fyers Secret ID", type="password", placeholder="Enter Secret ID")
    redirect_uri_input = st.text_input("Redirect URL", value="https://google.com")

    if client_id_input and secret_key_input:
        session = fyersModel.SessionModel(
            client_id=client_id_input.strip(),
            secret_key=secret_key_input.strip(),
            redirect_uri=redirect_uri_input.strip(),
            response_type="code",
            grant_type="authorization_code"
        )
        login_url = session.generate_authcode()
        st.markdown(f"**Step 1:** [Tap here to Log In to Fyers]({login_url})")
        
        redirected_url = st.text_input("Step 2: Paste the redirected Google URL here", placeholder="https://google.com...")
        
        if st.button("✅ Connect Live Feed", use_container_width=True):
            try:
                auth_code = redirected_url.split("auth_code=")[1].split("&")[0]
                session.set_token(auth_code)
                response = session.generate_token()
                if "access_token" in response:
                    st.session_state.access_token = response["access_token"]
                    st.session_state.client_id = client_id_input.strip()
                    st.success("Connected! Loading live market data...")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"Login failed: {response}")
            except Exception:
                st.error("Invalid URL pasted. Copy the full address bar URL after logging in.")

# --- MAIN DASHBOARD ---
if st.session_state.access_token:
    col1, col2 = st.columns([1.3, 1])
    with col1:
        auto_refresh = st.toggle("🔄 Auto-Refresh (60s)", value=True)
    with col2:
        if st.button("Refresh Now", use_container_width=True):
            st.rerun()

    fyers = fyersModel.FyersModel(
        client_id=st.session_state.client_id,
        token=st.session_state.access_token,
        is_async=False,
        log_path=""
    )

    sector_stocks = {
        "IT": ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM"],
        "Pvt Bank": ["HDFCBANK", "ICICIBANK", "AXISBANK", "KOTAKBANK", "INDUSINDBK"],
        "PSU Bank": ["SBIN", "BANKBARODA", "PNB", "CANBK", "UNIONBANK"],
        "Fin Service": ["BAJFINANCE", "BAJAJFINSV", "JIOFIN", "CHOLAFIN", "SHRIRAMFIN"],
        "Auto": ["TATAMOTORS", "MARUTI", "M&M", "BAJAJ-AUTO", "EICHERMOT"],
        "Pharma": ["SUNPHARMA", "CIPLA", "DRREDDY", "DIVISLAB", "APOLLOHOSP"],
        "Energy": ["RELIANCE", "ONGC", "NTPC", "POWERGRID", "COALINDIA"],
        "FMCG": ["ITC", "HINDUNILVR", "NESTLEIND", "BRITANNIA", "TATACONSUM"],
        "Metals": ["TATASTEEL", "HINDALCO", "JSWSTEEL", "VEDL", "NMDC"],
        "Realty": ["DLF", "LODHA", "GODREJPROP", "OBEROIRLTY", "PHOENIXLTD"],
        "Infra & Cement": ["LT", "ULTRACEMCO", "ADANIPORTS", "GRASIM", "AMBUJACEM"],
        "Media": ["ZEEL", "SUNTV", "PVRINOX", "NETWORK18", "NAZARA"]
    }

    symbol_to_sector = {}
    fyers_symbols = []
    for sector, stocks in sector_stocks.items():
        for stock in stocks:
            sym = f"NSE:{stock}-EQ"
            fyers_symbols.append(sym)
            symbol_to_sector[sym] = sector

    ist = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.now(ist)
    market_live = (now_ist.weekday() < 5) and (
        now_ist.replace(hour=9, minute=15, second=0) <= now_ist <= now_ist.replace(hour=15, minute=30, second=0)
    )

    if market_live:
        st.success(f"🟢 **LIVE FYERS FEED** • {now_ist.strftime('%I:%M:%S %p')} IST")
    else:
        st.warning(f"🔴 **MARKET CLOSED** (Showing Last Session) • {now_ist.strftime('%d %b, %I:%M %p')} IST")

    all_quotes = []
    for i in range(0, len(fyers_symbols), 50):
        batch = ",".join(fyers_symbols[i:i+50])
        response = fyers.quotes(data={"symbols": batch})
        if response.get("s") == "ok" and "d" in response:
            all_quotes.extend(response["d"])

    data = []
    for item in all_quotes:
        if item.get("s") == "ok":
            sym = item["n"]
            v = item["v"]
            today_open = float(v.get("open_price", 0))
            ltp = float(v.get("lp", 0))
            if today_open > 0:
                pct_change = ((ltp - today_open) / today_open) * 100
                data.append({
                    "Sector": symbol_to_sector[sym],
                    "Ticker": sym.replace("NSE:", "").replace("-EQ", ""),
                    "Open": round(today_open, 2),
                    "LTP": round(ltp, 2),
                    "Change (%)": round(pct_change, 2),
                    "Size": 1
                })

    if not data:
        st.error("Token expired or no data returned. Please log in again above.")
        st.session_state.access_token = ""
    else:
        df_map = pd.DataFrame(data)

        def highlight_change(val):
            color = '#188038' if val > 0 else ('#d93025' if val < 0 else '#5f6368')
            return f'color: {color}; font-weight: bold;'

        sector_summary = (
            df_map.groupby("Sector")
            .agg(
                Avg_Move=("Change (%)", "mean"),
                Gainers=("Change (%)", lambda x: (x > 0).sum()),
                Losers=("Change (%)", lambda x: (x < 0).sum())
            )
            .reset_index()
            .sort_values(by="Avg_Move", ascending=False)
            .reset_index(drop=True)
        )
        sector_summary["Avg_Move"] = sector_summary["Avg_Move"].round(2)
        ranked_sectors = sector_summary["Sector"].tolist()

        # --- 3 MOBILE TABS ---
        tab_heatmap, tab_sectors, tab_drilldown = st.tabs([
            "🗺️ Heatmap",
            "📊 Sectors & Movers",
            "🔍 Sector Stocks"
        ])

        with tab_heatmap:
            fig = px.treemap(
                df_map,
                path=[px.Constant("All NSE Sectors"), 'Sector', 'Ticker'],
                values='Size',
                color='Change (%)',
                color_continuous_scale=['#d93025', '#f1f3f4', '#188038'],
                color_continuous_midpoint=0,
                custom_data=['Open', 'LTP', 'Change (%)']
            )
            fig.update_traces(
                texttemplate="<b>%{label}</b><br>%{customdata[2]:+.2f}%",
                textfont=dict(size=13),
                hovertemplate="<b>%{label}</b><br>Open: ₹%{customdata[0]}<br>LTP: ₹%{customdata[1]}<br>Vs Open: %{customdata[2]:+.2f}%<extra></extra>"
            )
            fig.update_layout(height=720, margin=dict(t=10, l=5, r=5, b=5), coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True)

        with tab_sectors:
            st.subheader("Sector Ranking (Vs 9:15 AM Open)")
            st.caption("👆 Tap any sector row below to view its top performing stocks")

            sector_event = st.dataframe(
                sector_summary.style.map(highlight_change, subset=["Avg_Move"]).format({"Avg_Move": "{:+.2f}%"}),
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="sector_table_select"
            )

            selected_rows = sector_event.selection.rows
            chosen_sector = sector_summary.iloc[selected_rows[0]]["Sector"] if selected_rows else ranked_sectors[0]

            tapped_sector_df = (
                df_map[df_map["Sector"] == chosen_sector]
                .sort_values(by="Change (%)", ascending=False)[["Ticker", "Open", "LTP", "Change (%)"]]
                .reset_index(drop=True)
            )
            top_stock = tapped_sector_df.iloc[0]

            st.info(f"🏆 **Top Stock in {chosen_sector}:** **{top_stock['Ticker']}** ({top_stock['Change (%)']:+.2f}% • LTP ₹{top_stock['LTP']})")
            st.dataframe(
                tapped_sector_df.style.map(highlight_change, subset=["Change (%)"]).format({
                    "Open": "₹{:.2f}",
                    "LTP": "₹{:.2f}",
                    "Change (%)": "{:+.2f}%"
                }),
                use_container_width=True,
                hide_index=True
            )

            st.divider()
            sorted_stocks = df_map.sort_values(by="Change (%)", ascending=False)

            st.subheader("🚀 Top 5 Intraday Gainers (All Sectors)")
            gainers_df = sorted_stocks.head(5)[["Ticker", "Sector", "Open", "LTP", "Change (%)"]]
            st.dataframe(
                gainers_df.style.map(highlight_change, subset=["Change (%)"]).format({"Open": "₹{:.2f}", "LTP": "₹{:.2f}", "Change (%)": "{:+.2f}%"}),
                use_container_width=True,
                hide_index=True
            )

            st.subheader("🔻 Top 5 Intraday Losers (All Sectors)")
      
