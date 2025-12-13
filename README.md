# Indonesian Stock Market Prediction with Machine Learning 📈

System prediksi pasar saham Indonesia (IDX) otomatis menggunakan Machine Learning (LSTM & XGBoost). Project ini dibangun dengan arsitektur **Dockerized Microservices** yang mencakup pengumpulan data otomatis, pelatihan model, API, dan Dashboard interaktif.

## 🌟 Fitur Utama

*   **Automated Data Collection**: Mengambil data historis saham harian secara otomatis dari Yahoo Finance (via `yfinance`).
*   **Feature Engineering**: Perhitungan otomatis indikator teknikal (RSI, MACD, Bollinger Bands, SMA, EMA).
*   **Hybrid ML Models**: Menggunakan dua model sekaligus:
    *   **LSTM (Long Short-Term Memory)**: Untuk menangkap pola urutan (time-series) yang kompleks.
    *   **XGBoost**: Untuk regresi yang kuat dan efisien.
*   **Deep History & Context**: Dilatih dengan dataset **10 Tahun (2015-Kini)**, mencakup berbagai siklus pasar.
*   **Macro-Economic Awareness**: Mempertimbangkan pergerakan **IHSG (^JKSE)** dan **Kurs USD/IDR** sebagai konteks prediksi.
*   **Reproducible AI**: Menggunakan *Locked Random Seeds* untuk hasil training yang konsisten dan stabil.
*   **Interactive Dashboard**: UI berbasis Streamlit untuk memvisualisasikan data, sinyal Beli/Jual, dan kalkulasi Profit/Loss real-time.
*   **REST API**: Endpoint FastAPI untuk integrasi sistem lain.
*   **Containerized**: Setup mudah dengan Docker Compose (PostgreSQL, Redis, Python Services).

## 🛠️ Teknologi

*   **Bahasa**: Python 3.10
*   **Database**: PostgreSQL 15, Redis 7 (Caching)
*   **ML Framework**: TensorFlow (Keras), XGBoost, Scikit-learn
*   **Backend**: FastAPI, SQLAlchemy, Pydantic
*   **Frontend**: Streamlit, Plotly
*   **DevOps**: Docker, Docker Compose

## 📋 Prasyarat

*   **Docker Desktop** (Pastikan sudah terinstall dan berjalan).
*   Git (Opsional, untuk clone).

## 🚀 Cara Menjalankan (Quick Start)

1.  **Clone atau Buka Project**
    Pastikan Anda berada di direktori root project.

2.  **Konfigurasi Environment**
    Salin file contoh `.env` dan sesuaikan (minimal `DB_PASSWORD`):
    ```bash
    cp .env.example .env
    ```
    *Tips: Untuk lokal, password bebas (misal: `stockml123`).*

3.  **Jalankan dengan Docker**
    ```bash
    docker-compose up --build -d
    ```
    *Tunggu 5-10 menit untuk build pertama kali.*

4.  **Akses Aplikasi**
    *   **Dashboard**: [http://localhost:8505](http://localhost:8505)
    *   **API Docs**: [http://localhost:8005/docs](http://localhost:8005/docs)
    *   **Database**: Port `5435`

## 📂 Struktur Project

```
├── .env                # Variabel lingkungan (Password DB, API Keys)
├── docker-compose.yml  # Konfigurasi service Docker
├── src/
│   ├── api/            # Backend FastAPI
│   ├── dashboard/      # Frontend Streamlit
│   ├── data_collection/# Script pengumpul data (yfinance)
│   ├── feature_engineering/ # Logika indikator teknikal
│   ├── models/         # Definisi model LSTM & XGBoost
│   ├── training/       # Pipeline pelatihan model
│   └── utils/          # Fungsi bantu (DB, Logger)
├── scripts/            # Script inisialisasi (.sql)
└── docker/             # Dockerfile untuk setiap service
```

## 🔍 Troubleshooting

### 1. Docker Build Gagal (Disk Full)
Jika muncul error `input/output error` atau build macet:
*   Buka Docker Desktop -> Settings -> Resources -> Disk image location.
*   Klik **Clean / Purge data** (Hati-hati, ini menghapus semua data Docker).
*   Restart Docker dan jalankan `docker-compose up --build -d` lagi.

### 2. Data Saham Tidak Muncul
Cek log service `data_collector` untuk memastikan tidak ada error koneksi:
```bash
docker logs stock_ml_collector
```
Pastikan library `yfinance` sudah versi terbaru (sudah dihandle di `requirements.txt`).

### 3. Port Conflict
Jika port default bentrok, ubah di `docker-compose.yml`. Konfigurasi saat ini:
*   API: `8005`
*   Dashboard: `8505`
*   Postgres: `5435`

## 🧠 Penjelasan Fitur Dashboard

### 1. Tombol "Generate Prediction" 🔮
Tombol ini berfungsi untuk **meramal harga saham besok** berdasarkan data yang sudah dipelajari model.
*   **Cara Kerja**: Sistem mengambil 60 hari data terakhir dari database, lalu meminta model LSTM (yang sudah disimpan) untuk memprediksi 1 langkah ke depan.
*   **Kapan dipakai**: Saat Anda ingin tahu perkiraan harga penutupan (Close Price) untuk hari berikutnya.

### 2. Tombol "Retrain Model" 🔄
Tombol ini berfungsi untuk **mengajari ulang otak AI** dengan data terbaru.
*   **Cara Kerja**: Sistem akan mendownload data terbaru dari Yahoo Finance, lalu melatih ulang model LSTM & XGBoost dari nol menggunakan data tersebut. Model lama akan ditimpa dengan model baru yang lebih pintar.
*   **Kapan dipakai**: Lakukan ini secara berkala (misal seminggu sekali) agar AI tetap update dengan tren pasar terkini. *Proses ini berjalan di background dan butuh waktu beberapa menit.*

### 3. Metric Dashboard Intelligence 🧠
*   **Current Price**: Harga penutupan terakhir (Real).
*   **AI Target**: Prediksi harga penutupan berikutnya.
*   **Win Rate**: Persentase keberhasilan prediksi (Prediksi Arah Benar / Total Trades). *Akan 0% di awal sebelum ada history prediksi.*
*   **Error Margin**: Rata-rata selisih prediksi dengan harga asli dalam Rupiah (misal: ± Rp 300). Semakin kecil semakin akurat.
*   **Data Knowledge**: Berapa lama data historis yang dipelajari AI (misal: 10 Tahun). Menunjukkan "kematangan" model.

## 📊 Monitoring & Logs (Cek Log Manual)

Anda bisa memantau aktivitas setiap komponen secara real-time menggunakan perintah berikut di terminal:

| Komponen | Kegunaan | Perintah Log |
| :--- | :--- | :--- |
| **Data Collector** | Cek proses download data saham | `docker logs -f stock_ml_collector` |
| **ML Trainer** | Cek proses training model AI | `docker logs -f stock_ml_trainer` |
| **API Backend** | Cek request/response error | `docker logs -f stock_ml_api` |
| **Dashboard** | Cek error tampilan UI | `docker logs -f stock_ml_dashboard` |
| **Database** | Cek koneksi database | `docker logs -f stock_ml_db` |

**Tips:**
*   Gunakan `-f` (follow) agar log terus berjalan real-time. Tekan `Ctrl+C` untuk berhenti.
*   Log juga tersimpan otomatis di folder `logs/` di dalam project ini (bisa dibuka dengan text editor biasa).

## ☁️ Panduan Upload ke GitHub

Jika Anda ingin menyimpan kode ini ke repository GitHub Anda (`https://github.com/agee89/stock-market-id-ml.git`), ikuti langkah berikut di terminal project ini:

1.  **Inisialisasi Git (Jika belum)**
    ```bash
    git init
    ```

2.  **Cek Status & Tambahkan File**
    ```bash
    git status
    git add .
    git commit -m "Update project: Completed Phase 11 (Stability & Dashboard Upgrade)"
    ```

3.  **Pastikan Branch Utama Bernama 'main'**
    ```bash
    git branch -M main
    ```

4.  **Tambahkan Remote (Jika error 'already exists', abaikan)**
    ```bash
    git remote add origin https://github.com/agee89/stock-market-id-ml.git
    # Jika error "remote origin already exists", pastikan URL-nya benar:
    git remote set-url origin https://github.com/agee89/stock-market-id-ml.git
    ```

5.  **Push ke GitHub**
    ```bash
    git push -u origin main
    ```
    *(Jika diminta username/password, gunakan Personal Access Token, bukan password akun GitHub Anda).*

---
