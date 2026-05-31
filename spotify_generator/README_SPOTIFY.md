# 🟢 Spotify API Playlist Generator Bot

Modul pencari daftar lagu otomatis berbasis **Spotify API** resmi. Dengan modul ini, daftar lagu populer yang dihasilkan dijamin memiliki akurasi judul, ejaan penyanyi, dan tahun rilis 100% tepat sesuai database Spotify global.

---

## 🔑 Cara Mendapatkan Spotify Client ID & Client Secret (Gratis 2 Menit)

Untuk menggunakan bot ini, Anda membutuhkan kredensial API resmi yang gratis dari Spotify. Ikuti langkah mudah berikut:

1. **Masuk ke Portal Developer:**
   * Buka browser dan buka situs: [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
   * Login menggunakan akun Spotify biasa Anda (gratis maupun premium).

2. **Buat Aplikasi Baru (Create App):**
   * Klik tombol **"Create App"** di pojok kanan atas.
   * **App name:** Masukkan nama bebas, misal `Karaoke Generator`.
   * **App description:** Bebas, misal `Bot pencari list karaoke`.
   * **Redirect URI:** Masukkan `http://localhost:8080` (ini hanya formalitas, tidak akan dipakai).
   * Centang kotak persetujuan **API Terms of Service** dan klik **"Save"**.

3. **Ambil Client ID & Client Secret:**
   * Klik menu **"Settings"** di pojok kanan atas halaman aplikasi Anda.
   * Di sana Anda akan melihat **Client ID**.
   * Klik **"View client secret"** untuk menampilkan **Client Secret** Anda.
   * Salin kedua kode tersebut.

Saat Anda menjalankan `run_spotify_generator.bat` untuk pertama kali, bot akan mendeteksi kredensial yang kosong dan otomatis meminta Anda memasukkan kedua kode tersebut melalui terminal. Kredensial akan disimpan dengan aman di file `spotify_config.json`.

---

## 🚀 Cara Menjalankan Bot

1. Klik ganda file **`run_spotify_generator.bat`**.
2. Masukkan Client ID & Client Secret Anda saat diminta (hanya untuk pertama kali).
3. Masukkan rentang tahun pencarian (contoh: `2020-2026`).
4. Bot akan langsung melakukan pencarian berkecepatan tinggi ke Spotify API dan menyusun file Excel hasil bersih di dalam folder ini:
   * `list lagu spotify 2020-2026.xlsx`

5. Setelah list lagu bersih terbuat, Anda bisa langsung menyalin path file excel tersebut ke konfigurasi `config.json` di folder utama untuk mulai mengunduh karaoke!
