import streamlit as st
import requests
import pandas as pd
import os

API_URL = os.getenv("API_URL", "http://api:8000")

st.set_page_config(page_title="Market Scanner", page_icon="🔍", layout="wide")

st.title("🔍 Market Scanner")
st.caption("Scan top liquid stocks using Trader Checklist criteria.")

# Sidebar Controls
with st.sidebar:
    st.header("Scanner Settings")
    custom_symbols = st.text_area("Custom Symbols (Optional)", placeholder="BBCA.JK, ANTM.JK...")
    # Manual Trigger
    if st.button("🚀 Re-Scan Market"):
        st.session_state['scan_results'] = None
        st.rerun()

# Auto-Run Logic
if 'scan_results' not in st.session_state:
    st.session_state['scan_results'] = None

should_run = False
if st.session_state['scan_results'] is None:
     should_run = True

if should_run:
    scan_btn = True # Force True
else:
    scan_btn = False # Already have results

if scan_btn:
    symbols = []
    if custom_symbols.strip():
        symbols = [s.strip().upper() for s in custom_symbols.split(",") if s.strip()]
        
    with st.spinner("Scanning market (this takes ~10-20 seconds)..."):
        try:
            payload = {"symbols": symbols}
            response = requests.post(f"{API_URL}/scan", json=payload, timeout=60)
            
            if response.status_code == 200:
                data = response.json()
                
                # Convert to DataFrame for nice display
                rows = []
                for item in data:
                    if "error" in item: continue
                    
                    scores = item.get('scores', {})
                    details = item.get('details', {})
                    
                    # Extract key info
                    vol_liquid = any(d['label'] == 'Liquidity > 1B' and d['status'] == 'PASS' for d in details.get('volume', []))
                    
                    rows.append({
                        "Symbol": item['symbol'],
                        "Score": item['total_score'],
                        "Decision": item['decision'],
                        "Daily": scores.get('daily', 0),
                        "Hourly": scores.get('hourly', 0),
                        "15m": scores.get('15m', 0),
                        "Vol": scores.get('volume', 0),
                        "Fund": scores.get('fundamental', 0),
                        "Liquid": "✅" if vol_liquid else "❌",
                        "Action": item['symbol'] # Placeholder for button
                    })
                    
                df = pd.DataFrame(rows)
                st.session_state['scan_results'] = df
            else:
                st.error(f"Scan failed: {response.text}")
                
        except Exception as e:
            st.error(f"Error: {e}")

# Display Logic (Outside the running block)
if st.session_state['scan_results'] is not None:
    df = st.session_state['scan_results']
    
    # Display Metrics
    top_picks = df[df['Score'] >= 65]
    st.metric("Stocks Scanned", len(df))
    st.metric("Potential Trades (>65)", len(top_picks))
    
    st.divider()
    
    # Display Results
    st.subheader("📊 Scan Results")
    
    # Fetch Existing Stocks
    existing_symbols = set()
    try:
        r_stocks = requests.get(f"{API_URL}/stocks", timeout=5)
        if r_stocks.status_code == 200:
            existing_symbols = {s['symbol'] for s in r_stocks.json()}
    except:
        pass # Ignore error, just assume empty

    for index, row in df.iterrows():
        with st.container():
            c1, c2, c3, c4, c5, c6 = st.columns([1, 1, 3, 1, 1, 1])
            c1.markdown(f"**{row['Symbol']}**")
            c1.caption(row['Liquid'])
            
            score_color = "green" if row['Score'] >= 75 else "orange" if row['Score'] >= 50 else "red"
            c2.markdown(f":{score_color}[**{row['Score']}**]")
            
            if "TIDAK LAYAK" in row['Decision']:
                c3.error(row['Decision'], icon="🚫")
            elif "Daily Bearish" in row['Decision']:
                    c3.error(row['Decision'], icon="⚠️")
            else:
                c3.success(row['Decision'], icon="✅")
                
            # Breakdown
            c4.caption(f"D:{row['Daily']} H:{row['Hourly']} M:{row['15m']}")
            
            # Button Logic
            sym = row['Symbol']
            if sym in existing_symbols:
                c6.button("✅ Tracked", disabled=True, key=f"exist_{sym}")
            else:
                if c6.button("➕ Add", key=f"add_{sym}"):
                    try:
                        add_res = requests.post(f"{API_URL}/stocks", json={"symbol": sym})
                        if add_res.status_code == 200:
                            st.toast(f"✅ Added {sym} to Database!")
                            # Force reload next time to update 'tracked' status?
                            # For simple UX, just let toast show success.
                            # Ideally we update existing_symbols locally but streamlit rerun cleans it.
                            st.rerun() 
                        else:
                            st.toast(f"❌ Failed: {add_res.text}")
                    except Exception as e:
                        st.error(str(e))
                    
            st.divider()
elif not should_run:
    st.info("Click Re-Scan to update.")
