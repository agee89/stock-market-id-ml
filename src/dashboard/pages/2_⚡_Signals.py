import streamlit as st
import requests
import pandas as pd
import os
import concurrent.futures

API_URL = os.getenv("API_URL", "http://api:8000")

st.set_page_config(page_title="Active Signals", page_icon="⚡", layout="wide")

st.title("⚡ Active Signals")
st.caption("Real-time AI predictions for all tracked stocks.")

with st.expander("ℹ️  Panduan Membaca Sinyal & Strategi Trading"):
    st.markdown("""
    **Cara menggunakan informasi berdasarkan timeframe:**
    
    *   **Daily (Swing ✨):**
        *   **Gaya:** Santai / Tidak pantau setiap saat.
        *   **Hold:** 3 Hari - 2 Minggu.
        *   **Fokus:** Cari Profit > 5%. Abaikan fluktuasi kecil harian.
        *   **Validasi:** Cek Fundamental & News Sentiment di Dashboard detail.
    
    *   **Hourly (Intraday ⚡):**
        *   **Gaya:** Aktif harian. Masuk pagi/siang, usahakan keluar sebelum tutup pasar (T+0).
        *   **Hold:** Beberapa Jam.
        *   **Fokus:** Manfaatkan volatilitas harian (1% - 3%).
        *   **Validasi:** Pantau Volume & Arus uang.
    
    *   **15 Min (Scalping 🔥):**
        *   **Gaya:** Sangat Agresif. Butuh disiplin tinggi & koneksi cepat.
        *   **Hold:** 15 Menit - 1 Jam.
        *   **Fokus:** Curi poin cepat (0.5% - 1.5%). Jangan ragu Cut Loss ketat.
        *   **Validasi:** Momentum sesaat.
        
    **Kolom Penting:**
    *   **Target:** Harga tujuan ideal menurut AI dalam jangka waktu tersebut.
    *   **Stop Loss:** Titik keluar wajib jika harga bergerak berlawanan.
    *   **R:R (Risk Reward):** Idealnya **1:2**. Artinya potensi untung harus 2x lipat dari resiko rugi.
    """)

# Sidebar Settings
with st.sidebar:
    st.header("Signal Filters")
    # Timeframe Selector
    timeframe_map = {
        "Daily (Swing)": "1d",
        "Hourly (Intraday)": "1h",
        "15 Min (Day Trade)": "15m",
         "1 Min (Scalp)": "1m"
    }
    tf_label = st.selectbox("Timeframe", list(timeframe_map.keys()), index=1)
    interval = timeframe_map[tf_label]
    
    st.divider()
    min_conf = st.slider("Min Confidence/Profit %", 0.0, 5.0, 0.5, step=0.1)
    
    if st.button("🔄 Refresh Signals"):
        st.cache_data.clear()
        st.rerun()

# 1. Fetch All Stocks
@st.cache_data(ttl=60)
def get_all_stocks():
    try:
        res = requests.get(f"{API_URL}/stocks", timeout=5)
        if res.status_code == 200:
            return [s['symbol'] for s in res.json()], None
    except Exception as e:
        return [], str(e)
    return [], "Unknown Error"

symbols, error_msg = get_all_stocks()

# Filter out Indices/Currencies
if symbols:
    symbols = [s for s in symbols if s not in ['^JKSE', 'JKSE', 'IDR=X', 'USDIDR=X', '^DJI', '^IXIC', '^GSPC']]

if not symbols:
    st.error(f"No stocks found in database. API Error: {error_msg}")
    st.info(f"Connecting to: {API_URL}/stocks")
    st.stop()

# 2. Parallel Fetch Predictions
def fetch_prediction(symbol, interval):
    result_dict = {
        "symbol": symbol,
        "price": 0,
        "target": 0,
        "pct": 0,
        "date": "N/A",
        "status": "OK",
        "error": None
    }
    
    try:
        # 1. Get Real Price (Priority)
        # We need price regardless of prediction status
        hist_res = requests.get(f"{API_URL}/history/{symbol}?interval={interval}&limit=1", timeout=5)
        if hist_res.status_code == 200:
            h_data = hist_res.json()
            if h_data:
                result_dict['price'] = h_data[0]['close']

        # 2. Get Prediction
        pred_res = requests.get(f"{API_URL}/predict/{symbol}?interval={interval}", timeout=10)
        
        if pred_res.status_code == 200:
            data = pred_res.json()
            result_dict.update({
                "target": data.get('predicted_price', 0),
                "pct": data.get('expected_change_pct', 0),
                "date": data.get('target_date'),
                "status": "OK"
            })
        elif pred_res.status_code == 404:
            result_dict['status'] = "UNTRAINED"
            result_dict['error'] = "Model missing"
        else:
            result_dict['status'] = "ERROR"
            result_dict['error'] = f"API {pred_res.status_code}"
            
        return result_dict

    except Exception as e:
        result_dict['status'] = "FAIL"
        result_dict['error'] = str(e)
        return result_dict

results = []
progress_text = "Scanning AI Signals..."
my_bar = st.progress(0, text=progress_text)

with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor: # Reduce workers to avoid API overload
    futures = {executor.submit(fetch_prediction, sym, interval): sym for sym in symbols}
    
    completed = 0
    for future in concurrent.futures.as_completed(futures):
        completed += 1
        my_bar.progress(completed / len(symbols), text=f"Scanning {futures[future]}...")
        
        res = future.result()
        if res:
            results.append(res)
            
my_bar.empty()

# 3. Process & Display
if results:
    rows = []
    for r in results:
        current = r['price']
        target = r['target']
        pct = r['pct']
        status = r['status']
        
        # Default Values
        rec = "WAIT"
        rec_icon = "⚪"
        conf = "Low"
        sl_price = 0
        display_target = target
        display_pct = pct
        display_rr = "N/A"
        
        # Logic based on Status
        if status == "UNTRAINED":
            rec = "Untrained"
            rec_icon = "⚠️"
            conf = "N/A"
            # Keep price, but zero out target
            display_target = 0
            display_pct = 0
        elif status == "FAIL" or status == "ERROR":
            rec = "Error"
            rec_icon = "❌"
            conf = "N/A"
        else:
            # Normal Logic (OK)
            # Define threshold first (Restored)
            threshold = 0.5 if interval in ['1m', '15m'] else 2.0
            
            # Sense Check
            if abs(pct) > 50.0:
                rec = "⚠️ RETRAIN" 
                rec_icon = "🔧"
                conf = "Inv"
                display_pct = 0.0
                display_target = current 
                sl_price = current
                display_rr = "N/A"
            else:
                if pct > threshold: 
                    rec = "BUY"
                    rec_icon = "🟢"
                elif pct < -threshold:
                    rec = "SELL"
                    rec_icon = "🔴"
                else:
                    rec_icon = "⚪"
                
                # Stop Loss
                if pct > 0:
                    risk = (target - current) / 2
                    sl_price = current - risk
                    display_rr = "1:2"
                else:
                    risk = (current - target) / 2
                    sl_price = current + risk
                    display_rr = "1:2"
                
                conf = "High" if abs(pct) > (threshold * 2) else "Med" if abs(pct) > threshold else "Low"

        dashboard_url = f"http://localhost:8505/?symbol={r['symbol']}&interval={interval}"

        rows.append({
            "Kode": r['symbol'],
            "Rekomendasi": f"{rec_icon} {rec}",
            "Harga": current,
            "Target": display_target,
            "Stop Loss": sl_price,
            "Profit %": display_pct,
            "RR": display_rr,
            "Conf": conf,
            "Tanggal": r['date'], # Add Date for verification
            "Action": dashboard_url,
            "Debug": r.get('error', '')
        })
        
    df = pd.DataFrame(rows)
    
    # Filter: Show rows if Profit >= Min Conf OR if Status is not OK (Show Errors/Untrained)
    # We need to map 'Rekomendasi' back to Status or check a hidden column. 
    # Let's check 'Debug' column for errors, or relying on 'Profit %' being 0 is risky if min_conf is 0.
    # Better: Filter where (abs(Profit) >= min) OR (Debug != "") OR (Rekomendasi contains "⚠️")
    
    # Simpler: Create a boolean mask
    mask_profit = abs(df['Profit %']) >= min_conf
    mask_error = df['Rekomendasi'].str.contains("⚠️|❌|Empty") # Catch Untrained/Error icons
    
    df_show = df[mask_profit | mask_error]
    
    # Sort
    df_show = df_show.sort_values(by="Profit %", ascending=False)

    st.data_editor(
        df_show,
        column_config={
            "Kode": st.column_config.TextColumn("Symbol"),
            "Rekomendasi": st.column_config.TextColumn("Signal"),
            "Harga": st.column_config.NumberColumn("Price", format="Rp %.0f"),
            "Target": st.column_config.NumberColumn("Target", format="Rp %.0f"),
            "Stop Loss": st.column_config.NumberColumn("Stop Loss", format="Rp %.0f"),
            "Profit %": st.column_config.NumberColumn("Potensi %", format="%.2f%%"),
            "RR": st.column_config.TextColumn("R:R"),
            "Action": st.column_config.LinkColumn("Dashboard Link", display_text="Open ↗️"),
        },
        hide_index=True,
        use_container_width=True
    )
    
else:
    st.info("No signals found. Try retraining models.")
