# 📘 Best Practice: Panduan Efektif Menggunakan AI Trader

Dokumen ini berisi strategi terbaik untuk memaksimalkan profit dan meminimalisir risiko saat menggunakan aplikasi **Stock Market ID AI**.

---

## 1. Pemilihan Timeframe (Wajib Baca)
Berdasarkan arsitektur sistem (Logic Collector), berikut adalah karateristik setiap timeframe:

| Timeframe | Status | Deskripsi & Strategi |
| :--- | :--- | :--- |
| **Hourly (1H)** | ⭐ **TERBAIK** | **Sangat Direkomendasikan.** Sistem memiliki delay update ~10 menit. Pada candle 1 jam, delay ini tidak signifikan. Signal AI di sini paling seimbang antara kecepatan dan akurasi. Cocok untuk Swing Trading (Hold 1-3 hari). |
| **Daily (1D)** | ✅ **AMAN** | **Paling Stabil.** Zero noise. Gunakan untuk melihat tren besar. Jika Daily Bullish, maka trade di Hourly akan lebih sukses (Follow The Trend). |
| **15 Menit** | ⚠️ **RISIKO** | **Kurang Disarankan.** Karena delay sistem ~10 menit, saat signal muncul, candle 15m sudah hampir habis. Hanya gunakan untuk mencari titik entry presisi JIKA signal Hourly sudah hijau. |
| **1 Menit** | ❌ **HINDARI** | Data sering *lagging* dari Yahoo Finance. Terlalu banyak noise. |

---

## 2. Timing Entry (Kapan Harus Beli?)
Jangan masuk sembarangan. Ikuti **Aturan 3 Konfirmasi** di Dashboard:

1.  **Cek Banner AI (Kotak Hijau/Merah)**
    *   Jika kotak berwarna **HIJAU (BELI)**, catat **Harga Target**.
    *   Pastikan harga saat ini (Current Price) masih di bawah Target Price (Upside > 2%).

2.  **Validasi dengan Tab "AI Analyst"**
    *   Buka Tab `AI Analyst` -> Lihat bagian **"Deep Dive Analysis"**.
    *   Pastikan **Trend Status** adalah "UP" atau "SIDEWAYS-UP".
    *   Cek **Support Level**. Entry terbaik adalah saat harga *rebound* (memantul naik) di dekat area Support.

3.  **Cek Sentimen Berita (Tab News)**
    *   Pastikan Score Berita **Positif (> 0.2)**.
    *   Jika AI Signal "BELI" tapi Berita "Merah/Negatif", **HINDARI** (Bot mungkin belum merespon berita dadakan).

**⏰ Waktu Terbaik Cek Dashboard:**
*   Menit ke-12 setiap jam (Contoh: 09:12, 10:12, 11:12).
*   Sistem melakukan update data pada menit :11, jadi di menit :12 data sudah *fresh*.

---

## 3. Manajemen Risiko (Cut Loss & Take Profit)
AI memprediksi probabilitas, bukan kepastian. Anda wajib pasang pengaman.

*   **Stop Loss (SL):**
    *   Gunakan angka **Support** yang ada di Tab `AI Analyst`.
    *   Rumus Cepat: Pasang SL **2-3 ticks di bawah harga Low** candle sebelumnya.
    *   Jika Banner AI berubah jadi **MERAH (JUAL)**, segera jual tanpa tapi.

*   **Take Profit (TP):**
    *   Gunakan angka **Target Price** di Banner AI sebagai TP 1.
    *   Jika harga sudah naik +3% atau +5%, geser Stop Loss ke posisi impas (Trailing Stop) untuk mengunci profit.

---

## 4. Contoh Skenario Trading Sukses
**Skenario: Swing Trading Saham BBCA**

1.  **Pagi (09:15):** Buka Dashboard. Set Timeframe **Hourly**.
2.  **Cek:** Banner AI menunjukkan **"BELI"** dengan Target Rp 10.200. Harga sekarang Rp 9.800 (Potensi +4%).
3.  **Crosscheck:** Buka Tab `News`. Headlines menunjukkan sentimen positif tentang perbankan.
4.  **Execution:** Beli di Rp 9.800.
5.  **Pasang Pengaman:** Cek Tab `AI Analyst`, Support di Rp 9.600. Pasang Cut Loss di Rp 9.575.
6.  **Monitor:** Cek lagi jam 11:15 atau 14:15.
7.  **Exit:** Harga menyentuh Rp 10.150 sore hari. Jual (realisasi profit).

---

## 5. Mentalitas Trader AI
*   **AI adalah Co-Pilot, Anda Pilotnya.** Jangan terima mentah-mentah jika grafik terlihat mengerikan (bearish parah).
*   **Jangan FOMO.** Jika AI signal muncul tapi harga sudah naik tinggi mendekati target, **JANGAN KEJAR**. Tunggu koreksi (harga turun sedikit) baru masuk.
*   **Disiplin Jam.** Jangan trading di 10 menit pertama pembukaan (09:00-09:10) karena market sangat liar dan data sering belum stabil. Tunggu 09:15 ke atas.

Selamat Trading! 🚀
