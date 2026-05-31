# 🎵 YouTube Karaoke Downloader & Generator Suite

Dokumentasi lengkap sistem otomatisasi karaoke terintegrasi. Suite aplikasi ini dirancang khusus untuk mencari lagu populer secara massal berdasarkan tahun/genre, memverifikasi & membersihkan metadata lagu, serta mengunduh sekaligus mengompresi video karaoke dari YouTube secara portabel.

---

## 📌 Gambaran Umum Sistem

Sistem ini terdiri dari **tiga subsistem utama** yang bekerja secara estafet untuk menghasilkan pustaka lagu karaoke berkualitas tinggi:

```
[ 1. PLAYLIST GENERATOR ]
Menelusuri web & YouTube berdasarkan genre + rentang tahun.
Menghasilkan: list lagu new [TAHUN].xlsx
          ↓
[ 2. FILTER & CORRECTOR BOT ]
Menyaring kompilasi, memperbaiki format terbalik, dan mengoreksi tahun rilis asli via DuckDuckGo.
Menghasilkan: list lagu new rev final [TAHUN].xlsx
          ↓
[ 3. CORE DOWNLOADER ENGINE ]
Mengunduh video karaoke dari YouTube, mengonversi audio-visual,
serta mengompresi secara cerdas di bawah target ukuran (misal 19.5 MB).
Menghasilkan: Koleksi video .mp4 karaoke siap nyanyi!
```

---

## 🛠️ Modul 1: Playlist Generator Bot

Bot generator bertugas untuk mengumpulkan ribuan lagu populer dari YouTube secara massal dengan menggabungkan scraping DuckDuckGo (mencari artikel daftar lagu terpopuler) dan targeted YouTube searches.

### Fitur Utama:
* **Multi-threaded Worker (Paralel):** Memproses hingga 6 tugas genre/tahun secara bersamaan menggunakan pooling thread untuk kecepatan maksimal.
* **16 Kategori Genre Bawaan:** Mendukung pencarian sangat spesifik: *Indonesia Pop, Pop Punk, Rock, Barat, Dangdut, Jepang, Korea, Mandarin, Jawa Pop & Dangdut, Timur Indonesia, Arab, Malaysia, Hip Hop, Hiphop Dangdut, Reggae, dan Ska*.
* **Real-time Web UI Dashboard:** Menyediakan antarmuka dashboard modern yang bisa diakses di `http://localhost:8000` untuk memantau progres pencarian, statistik lagu terkumpul, log aktivitas worker, dan ETA secara langsung.
* **Database & History Checks:** Otomatis melewatkan lagu yang sudah pernah diunduh sebelumnya agar tidak terjadi duplikasi.
* **Penamaan File Berbasis Tahun:** Output Excel default otomatis dinamai sesuai rentang tahun pencarian, misalnya: `list lagu new 2020-2026.xlsx`.

---

## 🧼 Modul 2: Song List Filter & Corrector Bot

Bot ini dirancang khusus untuk memecahkan masalah umum data "ngaco" hasil scraping, seperti judul lagu kompilasi/medley non-karaoke, metadata tertukar, salah ejaan, atau tahun rilis yang tidak akurat.

### Fitur Utama:
* **Filter Lokal Heuristik:** Membaca file hasil generator dan langsung mengeliminasi lagu bertipe kompilasi, medley, nonstop, full album, best of, atau playlist menggunakan 25+ kata kunci penyaringan lokal.
* **Verifikasi Online Cerdas (DuckDuckGo HTML Scraping):**
  * **Koreksi Terbalik (Swapped):** Otomatis mendeteksi jika format penyanyi & judul lagu tertukar (misal: *Usai - Tiara Andini* menjadi *Tiara Andini - Usai*) berdasarkan hasil voting pola penulisan di mesin pencari.
  * **Penyelarasan Ejaan & Casing:** Menyelaraskan ejaan teks dan format kapitalisasi khusus band/singkatan (seperti `Tipe-X`, `BTS`, `IU`, `IVE`).
  * **Deteksi Tahun Rilis Asli:** Mengekstrak tahun rilis lagu yang sesungguhnya dari potongan artikel lirik/berita/Wikipedia hasil pencarian dan memperbarui kolom `Tahun`.
* **Sistem Caching Lokal (`filter_cache.json`):** Menyimpan hasil pencarian web agar pencarian lagu yang sama tidak dilakukan berulang kali (menghemat bandwidth dan menghindari limit IP).
* **Output Bersih Ganda:** Menghasilkan dua file output bersih:
  * `list lagu new rev [TAHUN].csv` (CSV bersih terfilter)
  * `list lagu new rev final [TAHUN].xlsx` (Excel final rapi dan terurut berdasarkan Kategori & Tahun).

---

## 📥 Modul 3: Core Downloader Engine

Engine utama yang memproses daftar Excel final untuk mendownload video karaoke, memisahkan/menggabungkan audio-video, serta mengompresinya agar muat di penyimpanan Anda dengan ukuran ideal.

### Fitur Utama:
* **Dynamic Bitrate Compression (< 19.5 MB):** Menggunakan rumus matematika FFmpeg untuk menghitung bitrate video dinamis berdasarkan durasi lagu agar ukuran file akhir konsisten di bawah target ukuran (misal 19.5 MB atau 10 MB) tanpa merusak kejernihan audio.
* **Resumable (Tahan Gangguan):** Riwayat unduhan dicatat di `download_history.json`. Jika komputer mati, mati lampu, atau internet putus, bot akan melanjutkan unduhan dari lagu terakhir yang sedang diproses tanpa mendownload ulang lagu yang sudah sukses.
* **Akselerasi GPU (Hardware Encoding):** Mendukung akselerasi GPU (seperti AMD `h264_amf`, NVIDIA `h264_nvenc`, atau Intel `h264_qsv`) untuk rendering kompresi video super cepat tanpa membebani CPU.
* **Auto-Switch Drive Aktif:** Jika drive tujuan utama penuh (ruang kosong < 500 MB), bot akan otomatis mencari drive alternatif berkapasitas terbesar di komputer Anda dan memindahkan jalur unduhan ke sana tanpa menghentikan antrean.
* **Penyimpanan Terstruktur:** Hasil unduhan disimpan dengan struktur yang sangat rapi:
  `D:\Karaoke_Downloads\{Kategori (Genre)}\{Penyanyi}\{Penyanyi} - {Judul Lagu}.mp4`

---

## 📁 Struktur Direktori Proyek

```
youtube_karaoke_downloader/
├── config.json                     # Konfigurasi global downloader (bitrate, GPU, dll)
├── download_history.json           # Riwayat unduhan sukses (database resumable)
├── requirements.txt                # Daftar dependensi Python
├── run.bat                         # Launcher utama Core Downloader
├── run_helper.bat                  # Helper untuk verifikasi environment
├── setup.ps1                       # Skrip otomatisasi install Python & FFmpeg portabel
│
├── python_embed/                   # Folder Python portabel (dibuat otomatis)
├── bin/                            # Folder FFmpeg portabel (dibuat otomatis)
│
├── generator/                      # Sub-folder generator & filter
│   ├── generate_list.py            # Kode sumber Playlist Generator Bot (Multi-threaded)
│   ├── filter_songs.py             # Kode sumber Song List Filter & Corrector Bot
│   ├── list_generator.py           # Helper parser judul & pencarian DDG generator
│   ├── filter_cache.json           # Cache lokal pencarian filter bot (dibuat otomatis)
│   ├── run_generator.bat           # Launcher Playlist Generator Bot
│   ├── run_filter.bat              # Launcher Song List Filter & Corrector Bot
│   ├── test_filter.py              # Unit test logika filter, swap, & koreksi tahun
│   └── test_validation.py          # Unit test logika parser judul & validasi online awal
│
└── src/                            # Kode sumber Downloader
    ├── main.py                     # Entry point program downloader
    └── downloader.py               # Engine pengunduh & kompresi FFmpeg
```

---

## 🚀 Alur Kerja Penggunaan End-to-End

Ikuti langkah-langkah di bawah ini untuk mengumpulkan dan mendownload video karaoke dari nol:

### Langkah 1: Kumpulkan Daftar Lagu Populer
1. Buka folder `generator` dan klik ganda file **`run_generator.bat`**.
2. Masukkan rentang tahun yang ingin dicari (contoh: `2020-2026`).
3. Pilih jumlah target lagu per genre (contoh: opsi `2` untuk 250 lagu/genre).
4. *(Opsional)* Buka browser Anda dan akses `http://localhost:8000` untuk memantau proses pencarian via Web UI Dashboard.
5. Setelah selesai, file daftar kotor akan tersimpan di:
   `generator/list lagu new 2020-2026.xlsx`

### Langkah 2: Bersihkan & Koreksi Daftar Lagu
1. Di dalam folder `generator`, klik ganda file **`run_filter.bat`**.
2. Bot akan mendeteksi file excel tahunan yang tersedia secara otomatis. Pilih nomor file yang ingin dibersihkan.
3. Pilih Mode Verifikasi:
   * **[1] Cepat & Selektif:** Hanya memeriksa lagu yang mencurigakan (Sangat direkomendasikan).
   * **[2] Deep Search:** Memeriksa seluruh lagu satu per satu ke web (Sangat akurat, butuh waktu lebih lama).
4. Bot akan menyaring seluruh lagu kompilasi, memperbaiki teks yang terbalik, menyelaraskan ejaan band, memperbarui tahun rilis asli, dan membuang duplikasi.
5. Hasil Excel final yang bersih akan tersimpan di:
   `generator/list lagu new rev final 2020-2026.xlsx`

### Langkah 3: Konfigurasi Downloader
Buka file `config.json` di root folder proyek dan sesuaikan pengaturannya:
```json
{
  "excel_path": "generator\\list lagu new rev final 2020-2026.xlsx",
  "target_size_mb": 19.5,
  "audio_bitrate_kbps": 192,
  "max_resolution": "720p",
  "min_disk_free_mb": 500,
  "max_workers": 6,
  "default_output_dir": "D:\\Karaoke_Downloads",
  "use_gpu_acceleration": true,
  "gpu_encoder": "h264_amf"
}
```
> **Catatan GPU Encoder:** Gunakan `h264_amf` untuk kartu grafis AMD, `h264_nvenc` untuk NVIDIA, atau `h264_qsv` untuk Intel.

### Langkah 4: Mulai Unduh Karaoke!
1. Di root folder proyek, klik ganda file **`run.bat`**.
2. Bot akan otomatis memverifikasi environment portabel, membaca file excel terfilter, lalu mengunduh serta mengompresi lagu karaoke secara paralel dengan aman.
3. Seluruh lagu karaoke siap pakai kini tersimpan rapi di harddisk Anda!

---

## 💡 Tips & Pemecahan Masalah

* **Menambah Artis Top Baru:** Anda dapat membuka file [generator/list_generator.py](file:///c:/Users/DIMPI/.gemini/antigravity-ide/scratch/youtube_karaoke_downloader/generator/list_generator.py) dan menambahkan nama penyanyi populer baru ke dictionary `TOP_ARTISTS` pada genre yang sesuai agar pencarian bot generator semakin terarah.
* **Menyaring Kata Kunci Baru:** Jika ada tipe lagu kompilasi baru yang lolos filter, buka file [generator/filter_songs.py](file:///c:/Users/DIMPI/.gemini/antigravity-ide/scratch/youtube_karaoke_downloader/generator/filter_songs.py) dan tambahkan kata kunci baru tersebut ke dalam list `COMPILATION_KEYWORDS`.
* **Mengulang Filter dari Awal:** Jika Anda ingin memaksa bot memverifikasi ulang lagu tanpa membaca data tersimpan, Anda cukup menghapus file `generator/filter_cache.json`.
