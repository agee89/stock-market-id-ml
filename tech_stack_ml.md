# 🧠 Technical Architecture: Machine Learning Stack

Dokumen ini menjelaskan detail teknis dari *Hybrid Intelligence System* yang digunakan dalam aplikasi ini. Arsitektur didesain untuk menangkap pola non-linear pasar saham Indonesia (IDX) dengan pendekatan kuantitatif.

---

## 1. Hybrid Model Architecture
Sistem menggunakan dua model berbeda yang dilatih secara bersamaan untuk setiap emiten dan timeframe.

### A. Deep Learning: LSTM (Long Short-Term Memory)
Model utama untuk menangkap dependensi jangka panjang (*Time-Series Sequential Patterns*).
*   **Library**: `TensorFlow / Keras 2.15`
*   **Input Shape**: `(Batch, 60, n_features)`
    *   *Sequence Length*: **60 Steps** (Melihat 60 candle ke belakang).
*   **Arsitektur**:
    1.  **Input Layer**: Menerima data terstandarisasi (`MinMaxScaled`).
    2.  **LSTM Layer 1**: 50 Unit, `return_sequences=True`.
    3.  **Dropout**: 0.2 (Mencegah overfitting).
    4.  **LSTM Layer 2**: 50 Unit, `return_sequences=False`.
    5.  **Dropout**: 0.2.
    6.  **Dense Layers**: 25 Unit -> 1 Unit (Output: *Scaled Price*).
*   **Fungsi**: Memprediksi arah tren utama berdasarkan sejarah pergerakan harga.

### B. Ensemble Learning: XGBoost
Model sekunder untuk validasi dan regresi presisi tinggi.
*   **Library**: `XGBoost 2.0`
*   **Metode**: Gradient Boosting Decision Trees.
*   **Input**: *Flattened Sequence* dari 60 candle terakhir.
*   **Fungsi**: Mendeteksi pola *Support/Resistance* kaku yang sering terlewat oleh LSTM.
*   *Catatan Deployment*: Saat ini XGBoost berjalan di background sebagai *Shadow Model* untuk validasi akurasi (Backtesting), sementara sinyal eksekusi utama diputuskan oleh LSTM.

---

## 2. Generative AI: DeepSeek LLM Analysis
Analisis sentimen berita tidak menggunakan metode klasik (*Bag-of-words*), melainkan menggunakan Large Language Model (LLM).

*   **Model Engine**: DeepSeek-V3 (via OpenAI-Compatible API).
*   **Prompt Engineering**: *Quantitative Financial Analyst Persona*.
*   **Input**: Kumpulan Judul Berita (Batch).
*   **Output**: Skor Floating Point `-1.0` (Extreme Fear) s.d `+1.0` (Extreme Greed).
*   **Integrasi**: Skor sentimen ini disimpan ke database dan diumpankan sebagai **Input Feature** ke dalam model LSTM, sehingga model bisa "belajar" korelasi antara berita dan harga.

---

## 3. Feature Engineering (14+ Dimensi)
Data mentah (OHLCV) diolah menjadi *multidimensional features* sebelum masuk ke model:

| Tipe Feature | Nama Indikator | Kegunaan Teoretis |
| :--- | :--- | :--- |
| **Trend** | MACD, MACD Signal | Mendeteksi momentum tren. |
| **Volatilitas** | Bollinger Bands (Upper/Lower) | Mengukur "kewajaran" harga (Overbought/Oversold). |
| **momentum** | RSI (14) | Sinyal jenuh beli/jual klasik. |
| **Volume** | Volume Change | Validasi kekuatan pergerakan harga. |
| **Sentiment** | `sentiment_score` (AI) | Faktor eksternal non-teknikal. |
| **Macro** | IHSG (`^JKSE`), USD/IDR (`IDR=X`) | Korelasi dengan pasar global/mata uang. |

---

## 4. MLOps & Training Pipeline
Sistem "Hidup" dan belajar sendiri secara berkala.

1.  **Data Collection**:
    *   Collector mengambil data setiap menit/jam.
    *   Safety Delay: 10-15 menit untuk memastikan validitas data *Closing Candle*.

2.  **Continuous Training (Active Learning)**:
    *   Setiap Siklus (1 Jam/Harian), Trainer mengecek data baru.
    *   Melakukan `fit()` ulang pada model LSTM.
    *   Menyimpan (Dump) model `.h5` dan `.joblib` (Scaler) versi terbaru.

3.  **Live Inference**:
    *   Prediktor memuat model & scaler terbaru.
    *   Mengambil data real-time, menghitung indikator, dan memberikan sinyal: **UP (Naik)** atau **DOWN (Turun)** beserta Target Price.

---

## 5. System Specifications
*   **Language**: Python 3.10
*   **Containerization**: Docker (Microservices: API, Dashboard, Trainer, Collector, DB, Redis).
*   **Database**: PostgreSQL 15 (TimescaleDB ready structure).
*   **Caching**: Redis 7 (Untuk performa Dashboard real-time).
