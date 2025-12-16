import streamlit as st
from streamlit import fragment
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import time
import os

# Configuration
API_URL = os.getenv("API_URL", "http://api:8000") # Use internal docker name by default

st.set_page_config(layout="wide", page_title="Stock Market ID AI Trader")

# Sidebar
st.sidebar.title("🤖 AI Trader Config")

# Timeframe Selector
# Timeframe Selector
timeframe_map = {
    "Daily": "1d",     # Investing
    "Hourly": "1h",    # Swing
    "15 Min": "15m",   # Day Trading
    "1 Min": "1m"      # Scalping
}
# Reverse map for lookup
val_to_label = {v: k for k, v in timeframe_map.items()}

# Persistent State via Query Params
try:
    # Streamlit >= 1.30 uses st.query_params as a dict-like object
    qp = st.query_params
    default_interval = qp.get("interval", "15m") # Default to 15m
except:
    # Fallback for older streamlit
    try:
        qp = st.experimental_get_query_params()
        default_interval = qp.get("interval", ["15m"])[0]
    except:
        default_interval = "15m"

# Find Label for the default interval
default_label = val_to_label.get(default_interval, "Daily")
# Get Index
tf_keys = list(timeframe_map.keys())
try:
    default_idx = tf_keys.index(default_label)
except:
    default_idx = 0

# UI: Radio Button (Locked look)
selected_tf_label = st.sidebar.radio(
    "Timeframe", 
    tf_keys, 
    index=default_idx,
)

# Update Logic & URL
selected_interval = timeframe_map[selected_tf_label]

try:
    st.query_params["interval"] = selected_interval
except:
    try:
        st.experimental_set_query_params(interval=selected_interval)
    except:
        pass

# Stock Selector
# Fetch Status
ml_status = "Idle"
# Add New Stock UI
with st.sidebar.expander("➕ Add New Stock"):
    new_symbol = st.text_input("Symbol (e.g. GOTO.JK)").upper().strip()
    if st.button("Add Stock"):
        if new_symbol:
            try:
                res = requests.post(f"{API_URL}/stocks", json={"symbol": new_symbol})
                if res.status_code == 200:
                    st.success(f"Added {new_symbol}!")
                    time.sleep(1)
                    st.rerun()
                elif res.status_code == 422: # Validation Error
                    st.error("Invalid Symbol format")
                else:
                     st.warning(res.json().get('message', 'Failed'))
            except Exception as e:
                st.error(f"Error: {e}")

stocks = []
stock_map = {}
try:
    res = requests.get(f"{API_URL}/stocks")
    if res.status_code == 200:
        data = res.json()
        stocks = [s['symbol'] for s in data if s['symbol'] not in ['IDR=X', '^JKSE']]
        # Create map for display: "BBCA.JK" -> "BBCA.JK (Bank Central Asia)"
        for s in data:
            name_display = s['name'] if s['name'] else "Unknown"
            # Truncate if too long
            if len(name_display) > 25:
                name_display = name_display[:25] + "..."
            stock_map[s['symbol']] = f"{s['symbol']} ({name_display})"

    # User Request: Default to ASII.JK
    if not stocks: # Should not happen if API works
         pass
    else:
        # Move ASII.JK to front if exists
        target = "ASII.JK"
        if target in stocks:
             stocks.insert(0, stocks.pop(stocks.index(target)))
             
except:
    st.sidebar.error("API Error: Cannot fetch stocks")

# Helper to format display
def format_stock_label(symbol):
    return stock_map.get(symbol, symbol)

if not stocks:
    st.sidebar.warning("Stocks list is empty.")
    selected_symbol = None
    
    # Empty State UI
    st.title("Welcome to Stock Market ID AI 🤖")
    st.info("👋 Halo! Belum ada saham yang dipantau.")
    st.markdown("""
    Silakan tambahkan kode saham (contoh: `BBCA.JK`, `GOTO.JK`) di menu **➕ Add New Stock** di Sidebar sebelah kiri.
    
    Aplikasi akan otomatis:
    1. 📥 Mengambil data historis
    2. 🧠 Melatih model AI
    3. 🔮 Memberikan prediksi & sinyal
    """)
    st.stop() # Stop execution here so the rest of the dashboard doesn't render with None

selected_symbol = st.sidebar.selectbox(
    "Select Stock", 
    stocks,
    format_func=format_stock_label
)

# AI Status Indicator
ml_status = "Idle"
status_color = "green"
try:
    s_res = requests.get(f"{API_URL}/status/{selected_symbol}")
    if s_res.status_code == 200:
        raw_status = s_res.json().get('status', 'Idle')
        if raw_status == "Running":
            status_color = "orange"
            ml_status = "Training / Improving..."
        else:
            ml_status = "Ready / Idle"
except:
    ml_status = "Unknown"
    status_color = "grey"

# Fetch System Status
global_status = "Idle"
try:
    g_res = requests.get(f"{API_URL}/status/system")
    if g_res.status_code == 200:
        raw_g = g_res.json().get('status', 'Idle')
        if "Training" in raw_g:
            global_status = raw_g # e.g. "Training BBCA.JK"

except:
    pass

# Determine display status priority
# If local is running -> show local
# If local idle but global busy -> show global (yellow)
# If both idle -> show idle
display_status = "Ready / Idle"
status_color = "green"

if ml_status == "Training / Improving...":
    display_status = ml_status
    status_color = "orange"
elif "Training" in global_status:
    display_status = f"System Busy ({global_status})"
    status_color = "orange"

st.sidebar.markdown(f"**🤖 AI Status:** :{status_color}[{display_status}]")





# Controls Area
col_refresh, col_space, col_filter = st.columns([1.5, 3, 2])

with col_refresh:
    # Align button with input field (approximate)
    st.write("") 
    st.write("") 
    if st.button("🔄 Refresh Data", use_container_width=True):
        pass # Button click triggers rerun automatically due to Streamlit nature

with col_filter:
    from datetime import timedelta
    today = datetime.now()
    
    # Preset Options
    presets = [
        "Last 7 Days", "Today", "Yesterday", "This Week", 
        "This Month", "Last 30 Days", "This Year", "All Time", "Custom"
    ]
    
    # Persist Index Logic
    default_ix = 0
    if "date_range_preset" in st.session_state:
        try:
            default_ix = presets.index(st.session_state["date_range_preset"])
        except: pass
        
    selected_preset = st.selectbox("Date Range", presets, index=default_ix, key="date_range_preset")
    
    start_date = None
    end_date = None

    if selected_preset == "Custom":
        date_range = st.date_input(
            "Select Range",
            value=(today - timedelta(days=7), today),
            format="DD/MM/YYYY"
        )
        start_date = date_range[0] if isinstance(date_range, tuple) and len(date_range) > 0 else None
        end_date = date_range[1] if isinstance(date_range, tuple) and len(date_range) > 1 else None
    elif selected_preset == "All Time":
        start_date = None
        end_date = None
    else:
        # Calculate based on preset
        new_end = today
        if selected_preset == "Today":
            new_start = today
        elif selected_preset == "Yesterday":
            new_start = today - timedelta(days=1)
            new_end = new_start
        elif selected_preset == "This Week":
            new_start = today - timedelta(days=today.weekday())
        elif selected_preset == "Last 7 Days":
            new_start = today - timedelta(days=7)
        elif selected_preset == "This Month":
            new_start = today.replace(day=1)
        elif selected_preset == "Last 30 Days":
            new_start = today - timedelta(days=30)
        elif selected_preset == "This Year":
            new_start = today.replace(month=1, day=1)
            
        start_date = new_start
        end_date = new_end

def get_market_status():
    """Determine IDX Market Status based on WIB (UTC+7)."""
    now_wib = datetime.now()
    
    # Weekend
    if now_wib.weekday() >= 5: # 5=Sat, 6=Sun
        return "🔴 TUTUP (Akhir Pekan)"
    
    h = now_wib.hour
    m = now_wib.minute
    t = h * 100 + m # 09:30 -> 930
    
    # Friday Schedule
    if now_wib.weekday() == 4:
        if t < 900: return "🔴 TUTUP (Pre-Open)"
        if 900 <= t < 1130: return "🟢 BUKA (Sesi 1)"
        if 1130 <= t < 1400: return "⏸️ ISTIRAHAT"
        if 1400 <= t < 1600: return "🟢 BUKA (Sesi 2)"
        return "🔴 TUTUP (Post-Close)"
    
    # Mon-Thu Schedule
    else:
        if t < 900: return "🔴 TUTUP (Pre-Open)"
        if 900 <= t < 1200: return "🟢 BUKA (Sesi 1)"
        if 1200 <= t < 1330: return "⏸️ ISTIRAHAT"
        if 1330 <= t < 1600: return "🟢 BUKA (Sesi 2)"
        return "🔴 TUTUP (Post-Close)"

def get_next_update_time():
    """Calculate next scheduled update time."""
    # Ensure WIB Time
    now = datetime.now()
    # Basic check: if year is 1970 or something, or just assume container is UTC?
    # Inspecting previous logs, it seems container might be UTC but we want WIB.
    # If we add 7h and it matches user observation, then container is UTC.
    # But user saw 16:56 (which matches 16:46 WIB). 
    # If container was UTC (09:46), next_min logic gives 09:56. 
    # User saw 16:56. This means 'now' WAS 16:46.
    # So 'datetime.now()' IS returning WIB.
    
    status = get_market_status()
    
    if "BUKA" in status or "ISTIRAHAT" in status:
         # Turbo Mode: Every 1 minute
         next_time = now + timedelta(minutes=1)
         return next_time.strftime("%H:%M WIB")
    else:
         # Market Closed
         return "Besok 09:00 WIB"

# Main Layout
# Use mapped name for title
display_title = stock_map.get(selected_symbol, selected_symbol)
st.title(f"📈 {display_title}")


# Function to fetch data
@st.cache_data(ttl=15)
def fetch_dashboard_data(symbol, interval, start_date=None, end_date=None, limit=100):
    data = {}
    
    # 1. Prediction
    try:
        pred_res = requests.get(f"{API_URL}/predict/{symbol}?interval={interval}")
        if pred_res.status_code == 200:
            data['prediction'] = pred_res.json()
    except Exception as e:
        # Don't error in cache function to avoid caching errors? 
        # Actually it's better to return what we have.
        pass
        
    # 2. History
    try:
        hist_res = requests.get(f"{API_URL}/history/{symbol}?interval={interval}")
        if hist_res.status_code == 200:
            data['history'] = hist_res.json()
    except Exception as e:
        pass
        
    # 3. Metrics (Model Performance)
    try:
        met_res = requests.get(f"{API_URL}/metrics/{symbol}?interval={interval}")
        if met_res.status_code == 200:
            data['metrics'] = met_res.json()
    except Exception as e:
        pass # Optional
        
    # 4. News (Daily only usually, but good for context)
    try:
        news_res = requests.get(f"{API_URL}/news/{symbol}")
        if news_res.status_code == 200:
            data['news'] = news_res.json()
    except:
        pass
        
    # 5. Signals
    # Format date for API
    start_str = start_date.strftime("%Y-%m-%d") if start_date else None
    end_str = end_date.strftime("%Y-%m-%d") if end_date else None
    
    try:
        # Append limit
        url = f"{API_URL}/signals/{symbol}?interval={interval}&limit={limit}"
        if start_str:
            url += f"&start_date={start_str}"
        if end_str:
            url += f"&end_date={end_str}"
            
        sig_res = requests.get(url)
        if sig_res.status_code == 200:
            data['signals'] = sig_res.json()
    except:
        pass
        
    # 6. Win Rate (Now Filtered!)
    try:
        url = f"{API_URL}/winrate/{symbol}?interval={interval}"
        if start_str:
            url += f"&start_date={start_str}"
        if end_str:
            url += f"&end_date={end_str}"
            
        wr_res = requests.get(url)
        if wr_res.status_code == 200:
            data['winrate'] = wr_res.json()
    except:
        pass
        
    return data

# Dynamic limit based on preset
limit = 500
if selected_preset in ["This Year", "Last 30 Days", "This Month"]:
    limit = 5000 
if selected_preset == "All Time":
    limit = 10000



data = fetch_dashboard_data(selected_symbol, selected_interval, start_date, end_date, limit)

# --- LIVE FRAGMENT: Top Metrics ---
@fragment(run_every=15)
def render_live_metrics(symbol, interval, start_date, end_date, limit):
    # Fetch Data (Cached)
    # We call it again inside the fragment, but cache handles it
    # AND because this function runs every 15s independently, it will fetch fresh data if cache expired.
    d = fetch_dashboard_data(symbol, interval, start_date, end_date, limit)
    
    # Update Status with Last Collect Time
    last_collect = "N/A"
    if 'history' in d and d['history']:
        try:
            dates = [pd.to_datetime(x['date']) for x in d['history']]
            if dates:
                last_date = max(dates)
                last_collect = last_date.strftime("%d-%b %H:%M WIB")
        except:
            pass

    next_update = get_next_update_time()
    market_status = get_market_status()
    
    # --- AI TRADE CALL (User Request: Large Instructions) ---
    if 'prediction' in d:
        p = d['prediction']
        pct = p.get('expected_change_pct', 0)
        target = p.get('predicted_price', 0)
        t_date = p.get('target_date', 'N/A')
        
        # Get Current Price
        curr = 0
        if 'history' in d and d['history']:
            curr = d['history'][0]['close']
            
        # Call Logic
        if pct > 0.2: # Mildly Bullish threshold
            call_color = "green"
            call_icon = "🟢"
            call_text = "BELI (BUY)"
            msg = f"Potensi NAIK menuju Target."
            container_func = st.success
        elif pct < -0.2:
            call_color = "red"
            call_icon = "🔴"
            call_text = "JUAL / HINDARI (SELL)"
            msg = f"Potensi TURUN/Koreksi."
            container_func = st.error
        else:
            call_color = "gray"
            call_icon = "⚪"
            call_text = "TUNGGU (WAIT)"
            msg = "Pasar Sideways atau belum ada konfirmasi kuat."
            container_func = st.warning
            
        with st.container():
            # Use columns to center or make it prominent
            c_call_1, c_call_2 = st.columns([2, 1])
            with c_call_1:
                container_func(f"### {call_icon} REKOMENDASI: {call_text}")
                st.markdown(f"**⏰ Waktu Target:** {t_date}")
            with c_call_2:
                st.metric("🎯 Target Harga", f"Rp {target:,.0f}", f"{pct:+.2f}%")
                st.caption(f"Entry/Current: Rp {curr:,.0f}")
                
    st.caption(f"Timeframe: {interval} | Model: LSTM + XGBoost | Last Data: {last_collect} | Next: {next_update} | Status: {market_status}")

    # Top Metrics Panel
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        current_price = 0
        if 'history' in d and d['history']:
            hist = d['history']
            current_price = hist[0]['close']
            current_price_date = pd.to_datetime(hist[0]['date']).strftime("%d-%b %H:%M WIB")
            
            # Calculate Change vs Previous Candle
            delta_str = None
            if len(hist) > 1:
                 prev_price = hist[1]['close']
                 chg = (current_price - prev_price) / prev_price * 100
                 diff = current_price - prev_price
                 delta_str = f"{chg:+.2f}% ({diff:,.0f})"

            st.metric("Current Price", f"Rp {current_price:,.0f}", delta_str)
            st.caption(f"Valid: {current_price_date}")
        else:
            st.metric("Current Price", "N/A")
            st.caption("Valid: N/A")

    with col2:
        if 'prediction' in d:
            pred = d['prediction']['predicted_price']
            change_pct = d['prediction']['expected_change_pct']
            delta = pred - current_price
            target_date = d['prediction'].get('target_date', 'N/A')
            if target_date != 'N/A':
                target_date = pd.to_datetime(target_date).strftime("%d-%b %H:%M WIB")
            st.metric("AI Target", f"Rp {pred:,.0f}", f"{change_pct:+.2f}% ({delta:,.0f})")
            st.caption(f"Target: {target_date}")
        else:
            st.metric("AI Target", "Waiting...")
            st.caption("Target: N/A")

    with col3:
        if 'winrate' in d:
            wr = d['winrate']['win_rate']
            total = d['winrate']['total_trades']
            st.metric("Win Rate", f"{wr:.1f}%", f"{total} Trades", delta_color="normal")
        else:
            st.metric("Win Rate", "N/A")

    with col4:
        if 'metrics' in d and d['metrics']:
            rmse = d['metrics']['rmse']
            st.metric("Error Margin", f"± Rp {rmse:,.0f}", delta_color="inverse")
        else:
            st.metric("Error Margin", "N/A")

    with col5:
        if 'metrics' in d and d['metrics']:
            samples = d['metrics'].get('training_samples', 0)
            years = samples / 250
            st.metric("Data Knowledge", f"{samples} Days", f"{years:.1f} Years")
        else:
            st.metric("Data Knowledge", "0 Days")

render_live_metrics(selected_symbol, selected_interval, start_date, end_date, limit)

# Fetch Data for Chart & Static Info (Cached)
data = fetch_dashboard_data(selected_symbol, selected_interval, start_date, end_date, limit)

# AI Intelligence Details
with st.expander("🧠 AI Brain Details (Model Metadata)", expanded=False):

    if 'metrics' in data and data['metrics']:
        m = data['metrics']
        
        # Calculate Maturity
        samples = m.get('training_samples', 0)
        if samples > 2000:
            maturity = "High (Mature)"
            color = "green"
        elif samples > 1000:
            maturity = "Medium (Developing)"
            color = "orange"
        else:
            maturity = "Low (Early Stage)"
            color = "red"
            
        # Parse Features
        import json
        features_list = []
        raw_features = m.get('features_used', [])
        features_list = []
        try:
            if isinstance(raw_features, list):
                features_list = raw_features
            elif isinstance(raw_features, str):
                features_list = json.loads(raw_features)
        except:
            features_list = []
            
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"**Data Maturity:** :{color}[{maturity}]")
            
            # Format Date (UTC -> WIB)
            t_date = m.get('training_date', 'N/A')
            try:
                if t_date != 'N/A':
                    dt = pd.to_datetime(t_date)
                    dt_wib = dt + pd.Timedelta(hours=7)
                    t_date = dt_wib.strftime("%d-%b %H:%M WIB")
            except:
                pass
            st.markdown(f"**Training Date:** {t_date}")
        with c2:
            st.markdown(f"**Model Version:** {m.get('version', 'v1')}")
            st.markdown(f"**Macro Awareness:** {'✅ ON' if 'ihsg_close' in features_list else '❌ OFF'}")
        with c3:
            st.markdown(f"**Features Count:** {len(features_list)}")
            st.caption(", ".join(features_list))
    else:
        st.warning("Model metadata not available. Please train the model first.")

# Chart Area
if 'history' in data and data['history']:
    df = pd.DataFrame(data['history'])
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date')
    
    # Figure creation moved below to handle Chart Slicing

    
    # Determine default zoom range based on interval
    from datetime import timedelta
    
    max_date = df['date'].max()
    min_date = df['date'].min()
    range_start = min_date
    
    # Logic for user-friendly default view
    if selected_interval == '1d':
        # Show last 6 months by default
        range_start = max_date - timedelta(days=180)
    elif selected_interval == '1h':
        # Show last 1 month (was 2 weeks)
        range_start = max_date - timedelta(days=30)
    elif selected_interval == '15m':
        # Show last 2 weeks (was 5 days)
        range_start = max_date - timedelta(weeks=2)
    elif selected_interval == '5m':
        # Show last 1 week (was 2 days)
        range_start = max_date - timedelta(weeks=1)
    elif selected_interval == '1m':
         # Show last 3 days (was 6 hours)
        range_start = max_date - timedelta(days=3)
        
    # Ensure start is within data bounds
    # Ensure start is within data bounds
    if range_start < min_date:
        range_start = min_date

    # --- MARKET HOURS INFO ---
    with st.expander("🕒 Jam Perdagangan Bursa (IDX) - Klik untuk detail"):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("##### 📅 Senin - Kamis")
            st.markdown("""
            - **Sesi 1**: 09:00 - 12:00 WIB (10:00 - 13:00 WITA)
            - **Istirahat**: 12:00 - 13:30 WIB (13:00 - 14:30 WITA)
            - **Sesi 2**: 13:30 - 16:00 WIB (14:30 - 17:00 WITA)
            """)
        with c2:
            st.markdown("##### 📅 Jumat")
            st.markdown("""
            - **Sesi 1**: 09:00 - 11:30 WIB (10:00 - 12:30 WITA)
            - **Istirahat**: 11:30 - 14:00 WIB (12:30 - 15:00 WITA)
            - **Sesi 2**: 14:00 - 16:00 WIB (15:00 - 17:00 WITA)
            """)
        st.info("ℹ️ *Data tidak akan update selama jam istirahat. Harap bersabar.*")

    # --- NEW: Focused View Logic ---
    st.caption("🔍 **Chart View Controls**")
    show_full_history = st.checkbox("Show Full History (Zoom Out)", value=False, help="Uncheck to focus only on recent data for better detail.")
    
    # 1. Slice DataFrame Check (Focus Mode)
    # Instead of just zooming, we actually FILTER the dataframe if the user doesn't want full history.
    # This solves the "lack of detail" issue by forcing Plotly to auto-scale ticks for the small range.
    chart_df = df.copy()
    if not show_full_history:
        chart_df = df[df['date'] >= range_start]
        
    # 2. X-Axis Tick Formatting (Intraday Detail)
    # Explicitly tell Plotly how to format the time labels
    dtick_format = None
    if selected_interval in ['1m', '5m', '15m', '1h']:
        dtick_format = "%H:%M\n%d-%b" # Show Hour:Minute and Date below
        
    if chart_df.empty:
        st.warning("No data available for the selected range. Try unchecking 'Show Full History' or changing the timeframe.")
    else:
        fig = go.Figure(data=[go.Candlestick(x=chart_df['date'],
                        open=chart_df['open'],
                        high=chart_df['high'],
                        low=chart_df['low'],
                        close=chart_df['close'],
                        name='Price')])
    
        # Calculate Y-Axis Range for the VISIBLE Window (chart_df)
        if not chart_df.empty:
            y_min = chart_df['low'].min()
            y_max = chart_df['high'].max()
            # Add 5% padding
            y_padding = (y_max - y_min) * 0.05
            y_range = [y_min - y_padding, y_max + y_padding]
        else:
            y_range = None # Auto
            
        # Define Rangebreaks (Hide non-trading time)
        rangebreaks = []
        # 1. Hide Weekends (Sat, Sun) - Universal
        rangebreaks.append(dict(bounds=["sat", "mon"])) 
        
        # 2. Hide Non-Trading Hours (Intraday only)
        # Be careful with mismatched patterns. 
        # IDX: Close 16:00, Open 09:00.
        if selected_interval not in ['1d', '1wk', '1mo']:
            rangebreaks.append(dict(bounds=[16, 9], pattern="hour")) # Hide 16:00 to 09:00
            
        fig.update_layout(
            title=f"{selected_symbol} - {selected_interval} Chart",
            xaxis_title="Date",
            yaxis_title="Price (IDR)",
            height=500,
            template="plotly_dark",
            margin=dict(l=0, r=0, t=40, b=0),
            xaxis=dict(
                rangeslider=dict(visible=False), # Disable range slider in Focus Mode to save space? Or Keep it? Let's keep it but optional.
                type="date",
                rangebreaks=rangebreaks,
                tickformat=dtick_format # Apply custom format
            ),
            yaxis=dict(
                range=y_range,
                autorange=False if y_range else True,
                fixedrange=False # Allow user to pan Y axis
            )
        )
        st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No historical data available. Please wait for the Collector to run.")

# History, News, Company & Analysis & Checklist Split
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📈 Live Signal", 
    "🧠 AI Analyst", 
    "🏢 Company Profile",
    "📰 News & Sentiment",
    "✅ Checklist"
])

with tab2:
    st.subheader("Deep Dive Analysis (Technical & Risk)")
    with st.spinner("Analyzing market structure..."):
        try:
            a_res = requests.get(f"{API_URL}/analysis/{selected_symbol}?interval={selected_interval}")
            if a_res.status_code == 200:
                ana = a_res.json()
                if "error" not in ana:
                    # Row 1: Key Metrics
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.markdown("### 💧 Likuiditas")
                        val_m = ana['liquidity']['avg_value_idr'] / 1000000
                        st.metric("Avg Transaction", f"Rp {val_m:,.0f} M")
                        st.caption(f"Status: **{ana['liquidity']['status']}**")
                        st.info("Tujuan: Memastikan saham mudah masuk & keluar.")
                    
                    with col2:
                        st.markdown("### 📈 Price Action")
                        st.metric("Trend", ana['trend']['status'])
                        st.caption(f"Support: {ana['setup']['support']:,.0f} | Resistance: {ana['setup']['resistance']:,.0f}")
                        st.info("Tujuan: Menentukan timing beli & jual.")

                    with col3:
                        st.markdown("### 🎢 Volatilitas")
                        st.metric("ATR (Range)", f"Rp {ana['volatility']['atr']:,.0f}")
                        st.caption(f"Volatility: **{ana['volatility']['label']}** ({ana['volatility']['pct']:.1f}%)")
                        st.info("Tujuan: Melihat peluang cuan & risiko.")

                    st.divider()
                    
                    # Row 2: Psychology & Plan
                    col4, col5 = st.columns(2)
                    with col4:
                        st.markdown("### 🧠 Psikologi Pasar")
                        rsi_val = ana['psychology']['rsi']
                        st.meter = st.progress(int(rsi_val))
                        st.metric("RSI (Momentum)", f"{rsi_val:.1f}", ana['psychology']['state'])
                        st.info("Tujuan: Tidak terjebak FOMO atau Panic Selling.")
                        
                    with col5:
                        st.markdown("### 🛡️ Manajemen Risiko (Plan)")
                        current_p = ana['price']
                        st.write(f"**Current Price:** Rp {current_p:,.0f}")
                        
                        st.markdown(f"""
                        *   **Cut Loss Area:** < Rp {ana['setup']['cut_loss']:,.0f}
                        *   **Target Profit:** > Rp {ana['setup']['target']:,.0f}
                        *   **Risk : Reward:** 1:2 (Conservative)
                        """)
                        st.info("Tujuan: Melindungi modal Anda.")

                else:
                    st.warning("Not enough data for analysis (Need > 50 candles).")
            else:
                st.error("Failed to fetch analysis.")
        except Exception as e:
            st.error(f"Analysis error: {e}")

with tab5:
    st.subheader("Trader Checklist (Short Term Focus)")


    with st.spinner("Analyzing Multi-Timeframe Data (Yahoo Finance)..."):
        try:
            check_res = requests.get(f"{API_URL}/checklist/{selected_symbol}")
            if check_res.status_code == 200:
                chk = check_res.json()
                if "error" not in chk:
                    # Header: Score & Decision
                    score = chk['total_score']
                    decision = chk['decision']
                    
                    c1, c2 = st.columns([1, 2])
                    with c1:
                        st.metric("Total Score", f"{score}/100")
                    with c2:
                        if "Daily Bearish" in decision:
                             st.error(f"⚠️ **{decision}**")
                             st.caption(f"Score analitikal: {score}, namun terhalang aturan Daily Bearish.")
                        elif "TIDAK LAYAK" in decision:
                             st.error(decision)
                        elif "LAYAK (TUNGGU" in decision:
                             st.warning(decision)
                        else:
                             st.success(decision)
                        
                    st.divider()
                    
                    # Details
                    details = chk['details']
                    
                    # 1. Daily
                    with st.expander("1️⃣ Daily Structure (Max 25)"):
                        for item in details['daily']:
                            icon = "✅" if item['status'] == 'PASS' else "❌"
                            st.write(f"{icon} **{item['label']}** (+{item['score']})")
                            if 'value' in item: st.caption(f"Value: {item['value']}")
                            
                    # 2. Hourly
                    with st.expander("2️⃣ Hourly Momentum (Max 25)"):
                        for item in details['hourly']:
                            icon = "✅" if item['status'] == 'PASS' else "❌"
                            st.write(f"{icon} **{item['label']}** (+{item['score']})")
                            if 'value' in item: st.caption(f"Value: {item['value']}")

                    # 3. 15m Entry
                    with st.expander("3️⃣ 15m Entry Trigger (Max 20)"):
                        for item in details['15m']:
                            icon = "✅" if item['status'] == 'PASS' else "❌" # Warn is also X for simplicity or ⚠️
                            if item['status'] == 'WARN': icon = "⚠️"
                            st.write(f"{icon} **{item['label']}** (+{item['score']})")
                            if 'value' in item: st.caption(f"Value: {item['value']}")

                    # 4. Volume
                    with st.expander("4️⃣ Volume & Liquidity (Max 15)"):
                        for item in details['volume']:
                            icon = "✅" if item['status'] == 'PASS' else "❌"
                            st.write(f"{icon} **{item['label']}** (+{item['score']})")
                            if 'value' in item: st.caption(f"Value: {item['value']}")

                    # 5. Catalyst
                    with st.expander("5️⃣ Catalyst & Fundamentals (Max 15)"):
                        for item in details['catalyst'] + details['fundamental']:
                            icon = "✅" if item['status'] == 'PASS' else "ℹ️"
                            if item['status'] == 'FAIL': icon = "❌"
                            st.write(f"{icon} **{item['label']}** (+{item['score']})")
                            if 'value' in item: st.caption(f"Value: {item['value']}")

                else:
                    st.error(f"Checklist Error: {chk.get('error')}")
            else:
                st.error("Failed to fetch checklist.")
        except Exception as e:
            st.error(f"Connection error: {e}")

with tab3:
    st.subheader("Company Information")
    with st.spinner("Fetching details..."):
        try:
            c_res = requests.get(f"{API_URL}/company/{selected_symbol}")
            if c_res.status_code == 200:
                c_data = c_res.json()
                if "error" not in c_data:
                    st.markdown(f"### {c_data['name']}")
                    col_c1, col_c2 = st.columns(2)
                    col_c1.info(f"**Sector:** {c_data['sector']}")
                    col_c2.info(f"**Industry:** {c_data['industry']}")
                    
                    st.markdown("#### Business Summary")
                    st.write(c_data['summary'])
                    
                    if c_data['website'] and c_data['website'] != '#':
                        st.markdown(f"🌐 [Visit Website]({c_data['website']})")
                else:
                    st.warning("Company details not available.")
            else:
                st.error("Failed to fetch company profile.")
        except Exception as e:
            st.error(f"Connection error: {e}")
        except Exception as e:
            st.error(f"Connection error: {e}")

with tab4:
    st.subheader(f"📰 AI News Sentiment: {selected_symbol}")
    
    # 1. Fetch News Data
    with st.spinner("Analyzing News..."):
        try:
            # We reuse the existing endpoint or query via direct DB access for speed?
            # Better to add an endpoint, but for now let's query DB directly via helper if possible
            # OR just assume 'news_sentiment' table is populated.
            # Real implementation: Call API /news/{symbol}
            news_res = requests.get(f"{API_URL}/news/{selected_symbol}")
            
            if news_res.status_code == 200:
                news_data = news_res.json()
                # ROBUST: Handle List vs Dict
                if isinstance(news_data, list):
                    articles = news_data
                else:
                    articles = news_data.get('articles', [])
                
                # 2. Display Top Score
                if articles:
                    # Score is same for batch usually, take first
                    score = articles[0].get('score', 0)
                    label = articles[0].get('sentiment', 'NEUTRAL')
                    
                    col_s1, col_s2 = st.columns([1, 3])
                    with col_s1:
                        st.metric("AI Sentiment Score", f"{score:.2f}", delta=label)
                    with col_s2:
                        if score > 0.5:
                            st.success(f"**EXTREMELY BULLISH** ({label})")
                            st.markdown("Market news is overwhelmingly positive.")
                        elif score > 0:
                            st.info(f"**MODERATELY BULLISH** ({label})")
                        elif score < -0.5:
                            st.error(f"**EXTREMELY BEARISH** ({label})")
                            st.markdown("Market news is overwhelmingly negative.")
                        elif score < 0:
                            st.warning(f"**MODERATELY BEARISH** ({label})")
                        else:
                            st.caption("**NEUTRAL**")
                            
                    st.divider()
                    
                    # 3. List Headlines
                    st.markdown("### 📢 Recent Headlines (Analyzed)")
                    for art in articles[:10]:
                        # Default to 0 if score missing
                        sc = art.get('score', 0)
                        s_icon = "🟢" if sc > 0 else "🔴" if sc < 0 else "⚪"
                        with st.expander(f"{s_icon} {art['title']}"):
                            st.caption(f"Source: {art['source']} | Date: {art['date']}")
                            st.write(f"Link: {art['url']}")
                            st.info(f"Individual Contribution: {sc}")
                else:
                    st.info("No recent news found for this stock.")
            else:
                st.warning("Could not fetch news data.")
        except Exception as e:
            st.error(f"News Error: {e}")
with tab1:
    @fragment(run_every=15)
    def render_live_history(symbol, interval, start_date, end_date, limit):
         # Fetch Data (Cached)
        d = fetch_dashboard_data(symbol, interval, start_date, end_date, limit)
        
        if 'signals' in d and d['signals']:
            st.subheader("Recent Signal Performance")
            
            # Show limit warning if needed
            if len(d['signals']) >= limit:
                st.warning(f"⚠️ Displaying last {limit} signals. Data truncated for performance.")
            
            # Create DataFrame
            sig_df = pd.DataFrame(d['signals'])
            
            # Create Price Map for Entry Lookup (Robust)
            price_map = {}
            if 'history' in d and d['history']:
                for h in d['history']:
                    try:
                        # Assuming API returns string dates, we fallback to pandas timestamp for matching
                        dt = pd.to_datetime(h['date'])
                        price_map[dt] = h['close']
                    except:
                        pass
            
            # Format Date
            try:
                sig_df['date'] = pd.to_datetime(sig_df['date'])
            except:
                pass 

            # Format columns
            def format_dir(val):
                return "🛒 BELI" if val == "UP" else "💰 JUAL"
                
            def format_market_dir(val):
                return "⬆️ NAIK" if val == "UP" else "⬇️ TURUN"

            # Apply basic transformations
            # 1. Result Logic (UI Side Correction)
            # 2. PnL Calculation (Standard Logic)
            # User Requirement: use entry price as base.
            # Formula: (Close - Entry) / Entry * 100% (for UP)
            
            def calc_metric(row):
                # Get Prices (Robustly)
                curr_actual = row.get('actual_price', 0)
                curr_entry = row.get('entry_price', 0)
                
                if not curr_entry or not curr_actual:
                    return 0.0
                
                # Formula
                # Percentage Change
                raw_pct = (curr_actual - curr_entry) / curr_entry
                
                # Direction Multiplier
                # If Prediction UP: Profit if raw_pct > 0
                # If Prediction DOWN: Profit if raw_pct < 0 (Price went down)
                direction = 1.0 if row['prediction'] == 'UP' else -1.0
                
                pnl = raw_pct * direction * 100.0
                return pnl

            # Ensure entry_price is calculated BEFORE PnL
            def get_entry_price(row):
                if row['date'] in price_map:
                    return price_map[row['date']]
                try:
                    pp = row['predicted_price']
                    pct = row['predicted_pct']
                    if pp and pct:
                         return pp / (1 + pct/100.0)
                except:
                    pass
                return 0

            sig_df['entry_price'] = sig_df.apply(get_entry_price, axis=1)
            sig_df['pnl'] = sig_df.apply(calc_metric, axis=1)

            # Updated Result & Market Logic based on Entry
            def get_result_label(row):
                # Check if trade is still Open/Waiting (No Close Price)
                entry = row.get('entry_price', 0)
                close = row.get('actual_price', 0)
                if not close or not entry: return "⏳ OPEN"
                
                # Based on PnL (for Closed trades)
                # Strict Logic: PnL > 0 is WIN. 
                # PnL <= 0 is LOSE (Even if Flat 0.00%, prediction failed to generate profit)
                if row['pnl'] > 0.0001: return "✅ WIN"
                return "❌ LOSE"
                
            def get_market_label(row):
                # Based on Close vs Entry
                entry = row.get('entry_price', 0)
                close = row.get('actual_price', 0)
                if not close or not entry: return "⏳ WAITING"
                
                if close > entry: return "⬆️ NAIK"
                if close < entry: return "⬇️ TURUN"
                return "➖ FLAT"

            sig_df['Result'] = sig_df.apply(get_result_label, axis=1)
            sig_df['Prediction'] = sig_df['prediction'].apply(format_dir)
            sig_df['Actual'] = sig_df.apply(get_market_label, axis=1)

            # Calculate Total PnL
            total_pnl = sig_df['pnl'].sum()
            
            # Display Total PnL
            st.metric("Total Realized Profit/Loss", f"{total_pnl:.2f}%", help="Calculated as (Close - Entry) / Entry")
            
            st.dataframe(
                sig_df,
                use_container_width=True,
                column_config={
                    "date": st.column_config.DatetimeColumn("Date", format="D MMM, HH:mm"),
                    "interval": "TF",
                    "entry_price": st.column_config.NumberColumn("Entry Price", format="Rp %.0f"),
                    "predicted_price": st.column_config.NumberColumn("Target Price", format="Rp %.0f"),
                    "predicted_pct": st.column_config.NumberColumn("Target %", format="%.2f%%"),
                    "actual_price": st.column_config.NumberColumn("Close Price", format="Rp %.0f"),
                    "Actual": "Market",
                    "actual_pct": st.column_config.NumberColumn("Market %", format="%.2f%%"),
                    "pnl": st.column_config.NumberColumn("Profit %", format="%.2f%%"),
                    "Result": "Status",
                    "Prediction": "Signal",
                },
                column_order=["date", "interval", "entry_price", "Prediction", "predicted_pct", "predicted_price", "Actual", "actual_price", "pnl", "Result"]
            )
        else:
            st.info("No trade history yet. Models are building backtest validation...")
            
    # Render the fragment
    render_live_history(selected_symbol, selected_interval, start_date, end_date, limit)

# Legacy News Block (Removed - Now in tab4)
# with tab2: ...

# Merged AI Analyst (DeepSeek) into tab2
with tab2:
    st.divider() # Separator between Technical & AI Text
    st.subheader("🤖 AI Trading Analyst (Generative DeepSeek)")
    st.info("Fitur ini menggunakan AI untuk menganalisa data Multi-Timeframe (Daily, H1, M15) secara real-time.")
    
    if "ai_analysis" not in st.session_state:
        st.session_state["ai_analysis"] = {}

    col_ai_btn, col_ai_info = st.columns([1, 4])
    
    with col_ai_btn:
        if st.button(f"🔎 Analyze {selected_symbol}", type="primary", use_container_width=True):
            with st.spinner(f"Meminta AI Menganalisa {selected_symbol}... (Estimasi 10-30 detik)"):
                try:
                    res = requests.get(f"{API_URL}/analysis/ai/{selected_symbol}", timeout=60)
                    if res.status_code == 200:
                        data = res.json()
                        st.session_state["ai_analysis"] = {
                            "symbol": selected_symbol,
                            "result": data.get("analysis", "No result.")
                        }
                    elif res.status_code == 502:
                         st.error("AI Service Error (Check API Key or Logs)")
                    else:
                        st.error(f"Error: {res.text}")
                except Exception as e:
                    st.error(f"Connection Error: {e}")

    # Display Result
    saved_analysis = st.session_state.get("ai_analysis", {})
    if saved_analysis.get("symbol") == selected_symbol and "result" in saved_analysis:
        st.markdown("---")
        st.markdown(saved_analysis["result"])
        
        if st.button("🗑️ Clear Analysis"):
            st.session_state["ai_analysis"] = {}
            st.rerun()
    elif saved_analysis:
        # Different symbol previously analyzed
        st.caption(f"Last analysis was for {saved_analysis.get('symbol')}. Click Analyze to refresh for {selected_symbol}.")

# Bottom Actions
st.divider()
st.subheader("⚙️ System Control")
if st.button(f"🚀 Force Retrain ({selected_interval})"):
    try:
        res = requests.post(f"{API_URL}/train/{selected_symbol}?interval={selected_interval}")
        if res.status_code == 200:
            st.success(f"Training started for {selected_symbol} {selected_interval}!")
        else:
            st.error("Failed to start training.")
    except Exception as e:
        st.error(f"Error: {e}")

st.markdown("---")
# Initialize state for delete confirmation
if "show_delete_confirm" not in st.session_state:
    st.session_state["show_delete_confirm"] = False

st.markdown("---")
st.subheader("🚨 Red Zone")
st.caption(f"Area Berbahaya: Menghapus data saham **{selected_symbol}** secara permanen.")

# Container for the UI
rez_zone = st.container()

if st.session_state["show_delete_confirm"]:
    with rez_zone:
        st.warning(f"⚠️ **KONFIRMASI PENGHAPUSAN: {selected_symbol}**")
        st.markdown("""
        Tindakan ini akan menghapus permanen:
        - ❌ Data Harga & Prediksi
        - ❌ History Trading & Sinyal
        """)
        
        c1, c2 = st.columns([3, 1])
        with c1:
            confirm_val = st.text_input("Ketik Kode Saham:", placeholder=selected_symbol, key="del_final_confirm")
        with c2:
            st.write("")
            st.write("")
            col_act_1, col_act_2 = st.columns(2)
            if col_act_1.button("BATAL", use_container_width=True):
                st.session_state["show_delete_confirm"] = False
                st.rerun()
                
            if col_act_2.button("🔥 HAPUS", type="primary", use_container_width=True):
                if confirm_val == selected_symbol:
                    try:
                        with st.spinner(f"Menghapus {selected_symbol}..."):
                            del_res = requests.delete(f"{API_URL}/stocks/{selected_symbol}")
                            if del_res.status_code == 200:
                                st.success("Terhapus!")
                                st.session_state["show_delete_confirm"] = False
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error(f"Gagal: {del_res.text}")
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.error("Kode salah.")

else:
    # Initial State: Show Delete Button
    col_rz_1, col_rz_2 = st.columns([3, 1])
    with col_rz_1:
         st.caption("Klik tombol di kanan untuk memulai proses penghapusan.")
    with col_rz_2:
        if st.button(f"🗑️ Hapus {selected_symbol}", type="primary", use_container_width=True):
             st.session_state["show_delete_confirm"] = True
             st.rerun()
