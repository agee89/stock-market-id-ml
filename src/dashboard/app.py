import streamlit as st
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
timeframe_map = {
    "Investing (Daily)": "1d",
    "Swing (Hourly)": "1h",
    "Day Trading (15m)": "15m",
    "Scalping (1m)": "1m"
}
selected_tf_label = st.sidebar.selectbox("Select Timeframe", list(timeframe_map.keys()))
selected_interval = timeframe_map[selected_tf_label]

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
        stocks = [s['symbol'] for s in data]
        # Create map for display: "BBCA.JK" -> "BBCA.JK (Bank Central Asia)"
        for s in data:
            name_display = s['name'] if s['name'] else "Unknown"
            # Truncate if too long
            if len(name_display) > 25:
                name_display = name_display[:25] + "..."
            stock_map[s['symbol']] = f"{s['symbol']} ({name_display})"
except:
    st.sidebar.error("API Error: Cannot fetch stocks")

# Helper to format display
def format_stock_label(symbol):
    return stock_map.get(symbol, symbol)

selected_symbol = st.sidebar.selectbox(
    "Select Stock", 
    stocks if stocks else ["BBCA.JK"],
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
        st.rerun()

with col_filter:
    from datetime import timedelta
    today = datetime.now()
    
    # Preset Options
    presets = [
        "Last 7 Days", "Today", "Yesterday", "This Week", 
        "This Month", "Last 30 Days", "This Year", "All Time", "Custom"
    ]
    
    selected_preset = st.selectbox("Date Range", presets)
    
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

# Main Layout
# Use mapped name for title
display_title = stock_map.get(selected_symbol, selected_symbol)
st.title(f"📈 Market Intelligence: {display_title}")
st.caption(f"Timeframe: {selected_interval} | Model: LSTM + XGBoost")

# Function to fetch data
def fetch_dashboard_data(symbol, interval, start_date=None, end_date=None, limit=100):
    data = {}
    
    # 1. Prediction
    try:
        pred_res = requests.get(f"{API_URL}/predict/{symbol}?interval={interval}")
        if pred_res.status_code == 200:
            data['prediction'] = pred_res.json()
    except:
        pass
        
    # 2. History
    try:
        hist_res = requests.get(f"{API_URL}/history/{symbol}?interval={interval}")
        if hist_res.status_code == 200:
            data['history'] = hist_res.json()
    except:
        pass
        
    # 3. Metrics (Model Performance)
    try:
        met_res = requests.get(f"{API_URL}/metrics/{symbol}?interval={interval}")
        if met_res.status_code == 200:
            data['metrics'] = met_res.json()
    except:
        pass
        
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

# Top Metrics Panel
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    current_price = 0
    if 'history' in data and data['history']:
        current_price = data['history'][0]['close']
        st.metric("Current Price", f"Rp {current_price:,.0f}")
    else:
        st.metric("Current Price", "N/A")

with col2:
    if 'prediction' in data:
        pred = data['prediction']['predicted_price']
        change_pct = data['prediction']['expected_change_pct']
        delta = pred - current_price
        st.metric("AI Target", f"Rp {pred:,.0f}", f"{change_pct:+.2f}% ({delta:,.0f})")
    else:
        st.metric("AI Target", "Waiting...")

with col3:
    if 'winrate' in data:
        wr = data['winrate']['win_rate']
        total = data['winrate']['total_trades']
        # Revert to standard metric. 
        # delta_color="normal" makes the delta (Trades) Green (if positive) or Red.
        st.metric("Win Rate", f"{wr:.1f}%", f"{total} Trades", delta_color="normal")
    else:
        st.metric("Win Rate", "N/A")

with col4:
    if 'metrics' in data and data['metrics']:
        rmse = data['metrics']['rmse']
        st.metric("Error Margin", f"± Rp {rmse:,.0f}", delta_color="inverse")
    else:
        st.metric("Error Margin", "N/A")

with col5:
    if 'metrics' in data and data['metrics']:
        samples = data['metrics'].get('training_samples', 0)
        # Assuming 1 year ~ 250 trading days
        years = samples / 250
        st.metric("Data Knowledge", f"{samples} Days", f"{years:.1f} Years")
    else:
        st.metric("Data Knowledge", "0 Days")

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
        
    fig = go.Figure(data=[go.Candlestick(x=chart_df['date'],
                    open=chart_df['open'],
                    high=chart_df['high'],
                    low=chart_df['low'],
                    close=chart_df['close'],
                    name='Price')])

    # Calculate Y-Axis Range for the VISIBLE Window (chart_df)
    # This prevents the chart from being flattened by old high/low prices
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
    rangebreaks.append(dict(bounds=["sat", "mon"])) # Hide Weekends
    if selected_interval not in ['1d', '1wk', '1mo']:
        rangebreaks.append(dict(values=["16:15", "08:45"])) # Hide Nights
        
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

# History, News, & Company Split
tab1, tab2, tab3 = st.tabs(["📜 Trade History", "📰 News & Sentiment", "🏢 Company Profile"])

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

with tab1:
    if 'signals' in data and data['signals']:
        st.subheader("Recent Signal Performance")
        
        # Show limit warning if needed
        if len(data['signals']) >= limit:
            st.warning(f"⚠️ Displaying last {limit} signals. Data truncated for performance.")
        
        # Create DataFrame
        sig_df = pd.DataFrame(data['signals'])
        
        # Format Date to WIB
        try:
            sig_df['date'] = pd.to_datetime(sig_df['date'])
            # sig_df['date'] = sig_df['date'] + pd.Timedelta(hours=7) # REMOVE: Historical data is already WIB
            sig_df['date'] = sig_df['date'].dt.strftime("%d-%b %H:%M") # Just format
        except Exception as e:
            pass # Keep original if failure

        # Format columns
        def format_dir(val):
            return "🛒 BELI" if val == "UP" else "💰 JUAL"
            
        def format_market_dir(val):
            return "⬆️ NAIK" if val == "UP" else "⬇️ TURUN"

        # Apply basic transformations
        def get_result_label(row):
            if row['is_win'] is None: 
                    return "⏳ WAITING"
            return "✅ WIN" if row['is_win'] else "❌ LOSE"
            
        # 1. Entry Price Calculation
        # PredPct = (Pred - Entry) / Entry  =>  Entry * (1 + Pct) = Pred  => Entry = Pred / (1 + Pct)
        # Note: Pct is percentage (e.g. 1.5). So divide by 100.
        sig_df['entry_price'] = sig_df.apply(
            lambda x: x['predicted_price'] / (1 + x['predicted_pct']/100.0) if x['predicted_price'] else None, 
            axis=1
        )

        sig_df['Result'] = sig_df.apply(get_result_label, axis=1)
        sig_df['Prediction'] = sig_df['prediction'].apply(format_dir)
        sig_df['Actual'] = sig_df['actual'].apply(lambda x: format_market_dir(x) if x else "N/A")
        
        # 2. PnL Calculation (Trade Result)
        # If Signal UP: PnL = ActualPct.
        # If Signal DOWN: PnL = -ActualPct (Short).
        # Note: actual_pct in data is (Actual - Entry)/Entry * 100
        def calc_pnl(row):
            if not row['actual_pct']: return 0.0
            direction_mult = 1.0 if row['prediction'] == 'UP' else -1.0
            return row['actual_pct'] * direction_mult

        sig_df['pnl'] = sig_df.apply(lambda x: calc_pnl(x), axis=1)
        
        # Calculate Total PnL
        total_pnl = sig_df['pnl'].sum()
        pnl_color = "normal" if total_pnl >= 0 else "inverse"
        
        st.metric("Total Realized Profit/Loss", f"{total_pnl:.2f}%", help="Sum of PnL from all displayed trades")
        
        st.dataframe(
            sig_df,
            use_container_width=True,
            column_config={
                "date": "Date",
                "interval": "TF",
                "entry_price": st.column_config.NumberColumn("Entry Price", format="Rp %.0f"),
                "predicted_price": st.column_config.NumberColumn("Target Price", format="Rp %.0f"),
                "actual_price": st.column_config.NumberColumn("Close Price", format="Rp %.0f"),
                "Prediction": "Signal",
                "Actual": "Market",
                "actual_pct": st.column_config.NumberColumn("Market %", format="%.2f%%"),
                "pnl": st.column_config.NumberColumn("Profit %", format="%.2f%%"),
                "Result": "Status"
            },
            column_order=["date", "interval", "entry_price", "Prediction", "predicted_price", "Actual", "actual_price", "pnl", "Result"]
        )
    else:
        st.info("No trade history yet. Models are building backtest validation...")

with tab2:
    if 'news' in data and data['news']:
        for news in data['news']:
            sentiment = news['sentiment']
            color = "🟢" if sentiment == "POSITIVE" else "🔴" if sentiment == "NEGATIVE" else "⚪"
            with st.expander(f"{color} {news['title']} ({news['date']})"):
                st.write(f"**Source:** {news['source']}")
                st.write(f"**Score:** {news['score']:.2f}")
                st.write(f"[Read Article]({news['url']})")
    else:
        st.info("No recent news found.")

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
