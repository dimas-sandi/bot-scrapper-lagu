import os
import sys
import json
import re
import csv
import urllib.request
import urllib.parse
import base64
import time
import colorama
import pandas as pd
from tqdm import tqdm
import threading
import http.server
import socketserver

colorama.init()

# Global variables for Web UI Dashboard (port 8001)
web_current_year = ""
web_current_genre = ""
web_collected_songs = []
web_running = False
web_songs_lock = threading.Lock()
server_port = 8001
downloaded_seen = set()

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Spotify Playlist Generator Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0b0f19;
            --card-bg: rgba(20, 30, 55, 0.5);
            --border-color: rgba(255, 255, 255, 0.08);
            --primary: #1db954;
            --primary-glow: rgba(29, 185, 84, 0.4);
            --secondary: #8b5cf6;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --text: #f3f4f6;
            --text-muted: #9ca3af;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Outfit', sans-serif;
            background-color: var(--bg-color);
            color: var(--text);
            overflow-x: hidden;
            background-image: 
                radial-gradient(circle at 10% 20%, rgba(29, 185, 84, 0.1) 0%, transparent 40%),
                radial-gradient(circle at 90% 80%, rgba(139, 92, 246, 0.1) 0%, transparent 40%);
            min-height: 100vh;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
        }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 2rem;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 1.5rem;
        }

        .logo {
            font-size: 1.8rem;
            font-weight: 800;
            background: linear-gradient(135deg, #1db954, #8b5cf6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .status-badge {
            background: rgba(29, 185, 84, 0.1);
            color: var(--primary);
            padding: 0.5rem 1rem;
            border-radius: 50px;
            font-size: 0.9rem;
            font-weight: 600;
            border: 1px solid rgba(29, 185, 84, 0.2);
            box-shadow: 0 0 15px var(--primary-glow);
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { box-shadow: 0 0 5px var(--primary-glow); }
            50% { box-shadow: 0 0 15px var(--primary-glow); }
            100% { box-shadow: 0 0 5px var(--primary-glow); }
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }

        .card {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.5rem;
            backdrop-filter: blur(10px);
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        }

        .card h3 {
            font-size: 0.9rem;
            text-transform: uppercase;
            color: var(--text-muted);
            margin-bottom: 0.5rem;
            font-weight: 600;
        }

        .card .val {
            font-size: 2rem;
            font-weight: 800;
            color: #fff;
        }

        .main-layout {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 1.5rem;
        }

        .songs-table-container {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.5rem;
            backdrop-filter: blur(10px);
            overflow: hidden;
            display: flex;
            flex-direction: column;
            max-height: 600px;
        }

        .table-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }

        .search-box {
            background: rgba(255,255,255,0.05);
            border: 1px solid var(--border-color);
            padding: 0.6rem 1rem;
            border-radius: 8px;
            color: #fff;
            font-family: inherit;
            width: 300px;
            outline: none;
            transition: all 0.3s;
        }

        .search-box:focus {
            border-color: var(--primary);
            box-shadow: 0 0 10px var(--primary-glow);
        }

        .table-wrapper {
            overflow-y: auto;
            flex-grow: 1;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
        }

        th {
            padding: 0.75rem 1rem;
            color: var(--text-muted);
            font-weight: 600;
            border-bottom: 1px solid var(--border-color);
            font-size: 0.9rem;
        }

        td {
            padding: 0.75rem 1rem;
            border-bottom: 1px solid rgba(255,255,255,0.03);
            font-size: 0.95rem;
        }

        .genre-stats-container {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.5rem;
            backdrop-filter: blur(10px);
            display: flex;
            flex-direction: column;
        }

        .stat-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.75rem;
            padding-bottom: 0.75rem;
            border-bottom: 1px solid rgba(255,255,255,0.03);
        }

        .stat-name {
            font-weight: 600;
        }

        .stat-count {
            background: rgba(29, 185, 84, 0.1);
            color: var(--primary);
            padding: 0.2rem 0.6rem;
            border-radius: 6px;
            font-size: 0.85rem;
            font-weight: 600;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="logo">🟢 Spotify Karaoke List Generator</div>
            <div class="status-badge" id="status-text">Menghubungkan...</div>
        </header>

        <div class="grid">
            <div class="card">
                <h3>Tahun Proses</h3>
                <div class="val" id="stat-year">-</div>
            </div>
            <div class="card">
                <h3>Kategori Aktif</h3>
                <div class="val" id="stat-genre" style="font-size: 1.5rem; line-height: 2.2rem;">-</div>
            </div>
            <div class="card">
                <h3>Lagu Terkumpul</h3>
                <div class="val" id="stat-songs">0</div>
            </div>
        </div>

        <div class="main-layout">
            <div class="songs-table-container">
                <div class="table-header">
                    <h2>Lagu Terkumpul</h2>
                    <input type="text" class="search-box" id="search-input" placeholder="Cari penyanyi atau judul...">
                </div>
                <div class="table-wrapper">
                    <table>
                        <thead>
                            <tr>
                                <th>Penyanyi</th>
                                <th>Judul Lagu</th>
                                <th>Kategori</th>
                                <th>Tahun</th>
                            </tr>
                        </thead>
                        <tbody id="songs-table-body">
                            <tr>
                                <td colspan="4" style="text-align: center; color: var(--text-muted); padding: 2rem;">Menunggu data...</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <div class="genre-stats-container">
                <h2 style="margin-bottom: 1rem;">Statistik Genre</h2>
                <div id="stats-wrapper">
                    <div style="color: var(--text-muted);">Belum ada data...</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let allSongs = [];
        async function updateDashboard() {
            try {
                let resp = await fetch('/data');
                let data = await resp.json();
                
                document.getElementById('status-text').innerText = data['running'] ? 'Sedang Mencari...' : 'Selesai';
                if (!data['running']) {
                    document.getElementById('status-text').style.boxShadow = 'none';
                    document.getElementById('status-text').style.background = 'rgba(255,255,255,0.05)';
                    document.getElementById('status-text').style.color = '#fff';
                    document.getElementById('status-text').style.animation = 'none';
                }
                
                document.getElementById('stat-year').innerText = data['current_year'] || '-';
                document.getElementById('stat-genre').innerText = data['current_genre'] || '-';
                document.getElementById('stat-songs').innerText = data['total_songs'];
                
                allSongs = data['songs'] || [];
                renderSongsTable();
                renderGenreStats(data['genre_stats']);
            } catch (e) {
                console.error(e);
            }
        }

        function renderSongsTable() {
            let searchVal = document.getElementById('search-input').value.toLowerCase();
            let tbody = document.getElementById('songs-table-body');
            let rowsHtml = '';
            
            let filtered = allSongs.filter(s => {
                let penyanyi = (s['Nama Penyanyi'] || '').toLowerCase();
                let judul = (s['Judul Lagu'] || '').toLowerCase();
                return penyanyi.includes(searchVal) || judul.includes(searchVal);
            });

            filtered.slice().reverse().forEach(s => {
                rowsHtml += `
                    <tr>
                        <td style="font-weight: 600; color: #fff;">${s['Nama Penyanyi']}</td>
                        <td>${s['Judul Lagu']}</td>
                        <td><span style="background: rgba(29,185,84,0.1); color: var(--primary); padding: 0.2rem 0.5rem; border-radius: 6px; font-size: 0.8rem; border: 1px solid rgba(29,185,84,0.2);">${s['Kategori']}</span></td>
                        <td style="color: var(--text-muted);">${s['Tahun']}</td>
                    </tr>
                `;
            });

            if (rowsHtml === '') {
                rowsHtml = '<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 2rem;">Tidak ada data lagu</td></tr>';
            }
            tbody.innerHTML = rowsHtml;
        }

        function renderGenreStats(stats) {
            let wrapper = document.getElementById('stats-wrapper');
            let html = '';
            for (let [cat, count] of Object.entries(stats || {})) {
                html += `
                    <div class="stat-row">
                        <span class="stat-name">${cat}</span>
                        <span class="stat-count">${count} lagu</span>
                    </div>
                `;
            }
            if (html === '') {
                html = '<div style="color: var(--text-muted);">Belum ada data...</div>';
            }
            wrapper.innerHTML = html;
        }

        document.getElementById('search-input').addEventListener('input', renderSongsTable);
        updateDashboard();
        setInterval(updateDashboard, 1500);
    </script>
</body>
</html>
"""

class WebUIRequestHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass # Suppress standard log output
        
    def do_GET(self):
        global web_current_year, web_current_genre, web_collected_songs, web_running
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode('utf-8'))
        elif self.path == '/data':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            with web_songs_lock:
                songs_copy = list(web_collected_songs)
                
            # Group stats
            genre_stats = {}
            for s in songs_copy:
                cat = s.get('Kategori', 'Lainnya')
                genre_stats[cat] = genre_stats.get(cat, 0) + 1
                
            data = {
                'current_year': web_current_year,
                'current_genre': web_current_genre,
                'total_songs': len(songs_copy),
                'running': web_running,
                'songs': songs_copy,
                'genre_stats': genre_stats
            }
            self.wfile.write(json.dumps(data).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

def start_web_ui_server(port=8001):
    global server_port
    server_port = port
    
    class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True
        def handle_error(self, request, client_address):
            pass
            
    while True:
        try:
            socketserver.TCPServer.allow_reuse_address = True
            server = ThreadingHTTPServer(('0.0.0.0', server_port), WebUIRequestHandler)
            t = threading.Thread(target=server.serve_forever, daemon=True)
            t.start()
            break
        except Exception:
            server_port += 1
            if server_port > 8090:
                break


colorama.init()

# Add parent directory to sys.path so we can import TOP_ARTISTS from list_generator
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from generator.list_generator import TOP_ARTISTS
except ImportError:
    # Fallback in case path resolver is different
    TOP_ARTISTS = {
        "Indonesia Pop": ["Lyodra", "Mahalini", "Tiara Andini", "Ziva Magnolya", "Andmesh", "Raim Laode", "Judika", "Noah", "Tulus", "Bernadya", "Sal Priadi", "Juicy Luicy"],
        "Pop Punk": ["Stand Here Alone", "Pee Wee Gaskins", "Rocket Rockers", "Superman Is Dead", "Closehead", "Blink-182", "Green Day", "Neck Deep", "Sum 41"],
        "Rock": ["Dewa 19", "Slank", "Kotak", "Jamrud", "Padi", "Gigi", "Coldplay", "Linkin Park", "Avenged Sevenfold"],
        "Barat": ["Taylor Swift", "Bruno Mars", "Billie Eilish", "Ed Sheeran", "Ariana Grande", "The Weeknd", "Justin Bieber", "Olivia Rodrigo", "Sabrina Carpenter"],
        "Dangdut": ["Lesti Kejora", "Happy Asmara", "Denny Caknan", "Guyon Waton", "Ndarboy Genk", "Yeni Inka", "Farel Prayoga", "Nella Kharisma"],
        "Jepang": ["Yoasobi", "Kenshi Yonezu", "Lisa", "Aimer", "Fujii Kaze", "One Ok Rock", "Radwimps", "Eve"],
        "Korea": ["BTS", "Blackpink", "NewJeans", "IVE", "Aespa", "TWICE", "Seventeen", "IU", "Stray Kids", "Le Sserafim"],
        "Mandarin": ["Jay Chou", "Eric Chou", "G.E.M.", "JJ Lin", "Teresa Teng", "Wang Leehom"],
        "Jawa Pop & Dangdut": ["Denny Caknan", "Happy Asmara", "Guyon Waton", "Ndarboy Genk", "Gilga Sahid", "Woro Widowati", "Aftershine"],
        "Timur Indonesia": ["Justy Aldrin", "Toton Caribo", "Mitha Talahatu", "Vicky Salamor", "M.A.C", "Glenn Sebastian"],
        "Arab": ["Maher Zain", "Humood Alkhudher", "Nancy Ajram", "Elissa", "Amr Diab"],
        "Malaysia": ["Siti Nurhaliza", "Exist", "Slam", "Iklim", "Ukays", "Search", "Thomas Arya"],
        "Hip Hop": ["Rich Brian", "Saykoji", "Laze", "Basboi", "Eminem", "Drake", "Kendrick Lamar"],
        "Hiphop Dangdut": ["NDX A.K.A", "Pendhoza", "Yogyakarta Hiphop Foundation", "Guyon Waton", "Denny Caknan"],
        "Reggae": ["Tony Q Rastafara", "Steven & Coconut Treez", "Dhyo Haw", "Ras Muhamad", "Bob Marley"],
        "Ska": ["Tipe-X", "Shaggydog", "Souljah", "The Skatalites", "Reel Big Fish"]
    }

CONFIG_FILE = "spotify_config.json"

# Mapped genre queries for Spotify search (using plain text, NOT genre: prefix which is unreliable)
GENRE_MAPS = {
    "Indonesia Pop": 'indonesian pop',
    "Pop Punk": 'pop punk',
    "Rock": 'rock',
    "Barat": 'pop',
    "Dangdut": 'dangdut',
    "Jepang": 'j-pop',
    "Korea": 'k-pop',
    "Mandarin": 'c-pop mandarin',
    "Jawa Pop & Dangdut": 'koplo jawa',
    "Timur Indonesia": 'pop timur indonesia',
    "Arab": 'arabic',
    "Malaysia": 'malaysian pop melayu',
    "Hip Hop": 'hip hop rap',
    "Hiphop Dangdut": 'dangdut hip hop',
    "Reggae": 'reggae',
    "Ska": 'ska punk'
}

IDEAL_DISTRIBUTION = [
    # (CountryName, DisplayName, ListOfQueries)
    ("Indonesia", "Indonesia", 
     ['indonesia', 'indonesian pop', 'indonesian rock', 'dangdut', 'koplo', 'pop jawa', 'indie indonesia']),
      
    ("Malaysia", "Malaysia", 
     ['malaysia', 'malaysian pop', 'melayu malaysia', 'pop melayu']),
     
    ("Mandarin", "Mandarin", 
     ['mandarin', 'cpop', 'chinese mandarin', 'mandarin pop']),
     
    ("Korea", "Korea", 
     ['kpop', 'korean pop', 'k-pop', 'k-pop hits']),
     
    ("Jepang", "Jepang", 
     ['jpop', 'japanese pop', 'j-pop', 'anime ost']),
     
    ("Amerika", "Amerika", 
     ['american pop', 'american rock', 'billboard pop', 'usa billboard', 'us charts']),
     
    ("Inggris", "Inggris", 
     ['british pop', 'british rock', 'uk pop', 'uk charts', 'britpop'])
]

# Map of sub-genres and their artists for writing metadata
SUBGENRES = {
    "Indonesia": [],
    "Malaysia": [],
    "Mandarin": [],
    "Korea": [],
    "Jepang": [],
    "Amerika": [],
    "Inggris": []
}

ARTIST_TO_SUBGENRE = {}
SUBGENRE_TO_COUNTRY = {
    "Indonesia": "Indonesia",
    "Malaysia": "Malaysia",
    "Mandarin": "Mandarin",
    "Korea": "Korea",
    "Jepang": "Jepang",
    "Amerika": "Amerika",
    "Inggris": "Inggris",
    "Artis Tambahan Khusus": "Indonesia"
}

def determine_genre(artist, country, track_title=""):
    return country


# ============================================================
#  DEEZER API FUNCTIONS (Free, no authentication required!)
# ============================================================

_album_date_cache = {}  # Cache album release dates to minimize API calls

def query_deezer(endpoint, params=None):
    """Generic Deezer API caller. No authentication needed!"""
    base_url = "https://api.deezer.com"
    url = base_url + endpoint
    if params:
        url += "?" + urllib.parse.urlencode(params)
    
    req = urllib.request.Request(url, headers={
        'Accept': 'application/json',
        'User-Agent': 'KaraokeListGenerator/1.0'
    })
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
                # Deezer returns error in JSON body, not HTTP status
                if isinstance(data, dict) and 'error' in data:
                    err = data['error']
                    if err.get('code') == 4:  # Rate limit
                        print(f"      {colorama.Fore.YELLOW}[Rate Limited] Menunggu 3 detik...{colorama.Style.RESET_ALL}")
                        time.sleep(3)
                        continue
                    return None
                return data
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(3)
                continue
            print(f"      {colorama.Fore.RED}[HTTP Error {e.code}]{colorama.Style.RESET_ALL}")
            return None
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            print(f"      {colorama.Fore.RED}[Error] Koneksi gagal: {str(e)[:80]}{colorama.Style.RESET_ALL}")
            return None
    return None

def deezer_search_tracks(query, limit=50, index=0):
    """Search tracks on Deezer. Returns list of track dicts or empty list."""
    res = query_deezer("/search", {"q": query, "limit": limit, "index": index, "order": "RANKING"})
    if res and 'data' in res:
        return res['data']
    return []

def deezer_search_artist(artist_name):
    """Search for an artist on Deezer. Returns artist dict or None."""
    res = query_deezer("/search/artist", {"q": artist_name, "limit": 1})
    if res and 'data' in res and len(res['data']) > 0:
        return res['data'][0]
    return None

def deezer_get_artist_top(artist_id, limit=100):
    """Get artist's top tracks from Deezer."""
    res = query_deezer(f"/artist/{artist_id}/top", {"limit": limit})
    if res and 'data' in res:
        return res['data']
    return []

def deezer_get_album_year(album_id):
    """Get album release year from Deezer (cached)."""
    if album_id in _album_date_cache:
        return _album_date_cache[album_id]
    res = query_deezer(f"/album/{album_id}")
    year = 0
    if res and 'release_date' in res:
        rd = res['release_date']
        if rd:
            try:
                year = int(rd.split('-')[0])
            except (ValueError, IndexError):
                pass
    _album_date_cache[album_id] = year
    return year

def parse_years_input(input_str):
    input_str = input_str.strip()
    years_list = []
    
    range_match = re.match(r'^(\d{4})\s*-\s*(\d{4})$', input_str)
    if range_match:
        start_year = int(range_match.group(1))
        end_year = int(range_match.group(2))
        if start_year > end_year:
            start_year, end_year = end_year, start_year
        years_list = list(range(start_year, end_year + 1))
    elif ',' in input_str:
        parts = input_str.split(',')
        for p in parts:
            p = p.strip()
            if p.isdigit() and len(p) == 4:
                years_list.append(int(p))
            elif p:
                raise ValueError(f"Format tahun '{p}' tidak valid.")
    elif input_str.isdigit() and len(input_str) == 4:
        years_list.append(int(input_str))
    else:
        raise ValueError("Format salah! Masukkan tahun tunggal (e.g. '2024'), rentang (e.g. '2020-2026'), atau list (e.g. '2020, 2022').")
        
    if not years_list:
        raise ValueError("Tidak ada tahun yang berhasil dibaca.")
            
    return sorted(list(set(years_list)))

def clean_track_name(name):
    """Removes standard remaster, live, and extra bracket details."""
    name = re.sub(r'[\(\[]\s*(remastered|remaster|live|radio edit|feat|acoustic|version|single|mono|stereo|bonus track)[^\]\)]*[\)\]]', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*-\s*(remastered|remaster|live|acoustic|radio edit|version).*$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def main():
    global downloaded_seen
    proj_dir = os.path.dirname(os.path.abspath(__file__))
    
    print(f"{colorama.Fore.GREEN}=========================================================={colorama.Style.RESET_ALL}")
    print(f"       MUSIC API PLAYLIST GENERATOR BOT (Deezer)          ")
    print(f"{colorama.Fore.GREEN}=========================================================={colorama.Style.RESET_ALL}")
    
    # 1. Test Deezer API connection
    print(" Menghubungkan ke Deezer API (gratis, tanpa autentikasi)...")
    test = query_deezer("/genre")
    if test is None:
        print(f"{colorama.Fore.RED} [Error] Gagal terhubung ke Deezer API. Periksa koneksi internet.{colorama.Style.RESET_ALL}")
        sys.exit(1)
    print(f"{colorama.Fore.GREEN} -> Koneksi Deezer API Berhasil!{colorama.Style.RESET_ALL}")
    
    # 2. Get Years Input
    while True:
        input_str = input(f"\n Masukkan tahun (Contoh: '2024', '2020-2026', '2020, 2022'): ").strip()
        try:
            years = parse_years_input(input_str)
            break
        except ValueError as e:
            print(f"{colorama.Fore.RED} [Error] {str(e)}{colorama.Style.RESET_ALL}")
            
    years_disp = ", ".join(map(str, years))
    print(f" -> Tahun yang akan dicari: {colorama.Fore.GREEN}{years_disp}{colorama.Style.RESET_ALL} (total {len(years)} tahun)")
    
    # Setup filenames
    if len(years) == 1:
        years_suffix = f"{years[0]}"
    else:
        years_suffix = f"{min(years)}-{max(years)}"
        
    xlsx_filename = f"list lagu spotify {years_suffix}.xlsx"
    csv_filename = f"list lagu spotify {years_suffix}.csv"
    xlsx_path = os.path.join(proj_dir, xlsx_filename)
    csv_path = os.path.join(proj_dir, csv_filename)
    
    # 2. Get Target Song Count
    print(f"\n {colorama.Fore.CYAN}Masukkan target TOTAL lagu yang ingin dikumpulkan secara keseluruhan:{colorama.Style.RESET_ALL}")
    print(" - Masukkan angka (Contoh: '1000', '5000') untuk membatasi kuota lagu secara proporsional.")
    print(" - Tekan Enter atau ketik 'semua' / 'all' untuk mengambil semua lagu tanpa batasan kuota.")
    
    total_target_input = input(" Target total lagu (default semua): ").strip().lower()
    
    unlimited_mode = False
    total_target_songs = 1000
    
    if not total_target_input or total_target_input in ('semua', 'all'):
        unlimited_mode = True
        print(f" -> {colorama.Fore.GREEN}Mode TANPA BATAS (\"semua\") aktif.{colorama.Style.RESET_ALL} Mengambil semua lagu yang tersedia.")
    else:
        if total_target_input.isdigit() and int(total_target_input) > 0:
            total_target_songs = int(total_target_input)
        else:
            total_target_songs = 1000
        print(f" -> Target total lagu: {colorama.Fore.GREEN}{total_target_songs}{colorama.Style.RESET_ALL} lagu.")
        
    # Prompt for optional additional custom artists
    print(f"\n {colorama.Fore.CYAN}Apakah ada artis/penyanyi baru/tambahan yang ingin dicari secara khusus?{colorama.Style.RESET_ALL}")
    print(" - Masukkan nama artis dipisah koma (Contoh: 'Bernadya, Sal Priadi').")
    print(" - Atau tekan Enter jika tidak ada.")
    custom_artists_input = input(" Artis tambahan khusus (opsional): ").strip()
    
    custom_artists = []
    if custom_artists_input:
        custom_artists = [x.strip() for x in custom_artists_input.split(',') if x.strip()]
        print(f" -> Artis tambahan khusus: {colorama.Fore.GREEN}{', '.join(custom_artists)}{colorama.Style.RESET_ALL}")
        
    num_years = len(years)
    selected_genres = {} # Format: {Category_Name: {"queries": [...], "artists": [...]}}
    
    # Prepend custom artists if provided
    if custom_artists:
        selected_genres["Artis Tambahan Khusus"] = {
            "queries": ["pop"],
            "artists": custom_artists
        }
        
    for country_name, display_name, queries_list in IDEAL_DISTRIBUTION:
        selected_genres[country_name] = {
            "queries": queries_list,
            "artists": []
        }
        
    # 3. Core Search Process (Deezer API)
    # Global dedup set to prevent songs appearing in multiple categories
    global_seen = set()
    
    # Global accumulator for results
    all_tracks = []
    
    # Load download history if exists to prevent duplicates
    history_path = os.path.join(os.path.dirname(proj_dir), "download_history.json")
    if os.path.exists(history_path):
        try:
            with open(history_path, 'r', encoding='utf-8') as f:
                history_data = json.load(f)
                for key in history_data.keys():
                    downloaded_seen.add(key.lower().strip())
            print(f" -> {colorama.Fore.GREEN}Berhasil memuat {len(downloaded_seen)} lagu dari riwayat download (download_history.json).{colorama.Style.RESET_ALL}")
        except Exception as e:
            print(f" {colorama.Fore.RED}[Warning] Gagal membaca download_history.json: {e}{colorama.Style.RESET_ALL}")
    
    # Load progress from CSV if exists to enable resume functionality
    loaded_count = 0
    if os.path.exists(csv_path):
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    t_artist = row.get('Nama Penyanyi', '')
                    t_title = row.get('Judul Lagu', '')
                    t_cat = row.get('Kategori', '')
                    try:
                        t_year = int(row.get('Tahun', 0))
                    except:
                        t_year = 0
                    
                    dup_key = f"{t_artist.lower().strip()} - {t_title.lower().strip()}"
                    if dup_key not in global_seen:
                        global_seen.add(dup_key)
                        track_item = {
                            'Nama Penyanyi': t_artist,
                            'Judul Lagu': t_title,
                            'Kategori': t_cat,
                            'Tahun': t_year
                        }
                        all_tracks.append(track_item)
                        loaded_count += 1
            print(f" -> {colorama.Fore.GREEN}Berhasil memuat {loaded_count} lagu dari progress CSV untuk resume.{colorama.Style.RESET_ALL}")
            print(f"    (Jika ingin memulai ulang dari awal, silakan hapus file CSV tersebut)")
        except Exception as e:
            print(f" {colorama.Fore.RED}[Warning] Gagal membaca progress CSV: {e}{colorama.Style.RESET_ALL}")
            
    # Start Web UI Server in background
    global web_running, web_current_year, web_current_genre, web_collected_songs
    web_running = True
    start_web_ui_server(port=8001)
    
    print(f"  Live Web UI Dashboard: {colorama.Fore.CYAN}http://localhost:{server_port}{colorama.Style.RESET_ALL}")
    print(f"{colorama.Fore.GREEN}----------------------------------------------------------{colorama.Style.RESET_ALL}")
    
    # Cache for artist IDs on Deezer
    artist_id_cache = {}
    
    def _add_deezer_track(track, category_name, target_year):
        """Process a Deezer track result and add to genre_tracks if valid."""
        global web_collected_songs, downloaded_seen
        t_title = clean_track_name(track.get('title', '') or track.get('title_short', ''))
        if not t_title:
            return False
        
        # Get artist info
        artist_info = track.get('artist', {})
        t_artist = artist_info.get('name', 'Unknown')
        
        dup_key = f"{t_artist.lower().strip()} - {t_title.lower().strip()}"
        if dup_key in seen_local or dup_key in global_seen or dup_key in downloaded_seen:
            return False
        
        # Get release year from album (use cache to minimize API calls)
        album_info = track.get('album', {})
        album_id = album_info.get('id', 0)
        track_year = 0
        if album_id:
            track_year = deezer_get_album_year(album_id)
        
        # Year filter: allow ±1 year tolerance, or accept if year unknown
        if track_year > 0 and target_year > 0:
            if abs(track_year - target_year) > 1:
                return False
        
        seen_local.add(dup_key)
        global_seen.add(dup_key)
        
        final_year = track_year if track_year > 0 else target_year
        
        # Determine specific sub-genre metadata for saving
        determined_subgenre = determine_genre(t_artist, category_name, t_title)
        
        track_item = {
            'Nama Penyanyi': t_artist,
            'Judul Lagu': t_title,
            'Kategori': determined_subgenre,
            'Tahun': final_year,
            'Popularity': track.get('rank', 0)
        }
        genre_tracks.append(track_item)
        
        # Live update Web UI
        with web_songs_lock:
            current_temp = []
            for gt in genre_tracks:
                gt_copy = dict(gt)
                gt_copy.pop('Popularity', None)
                current_temp.append(gt_copy)
            web_collected_songs = all_tracks + current_temp
        return True
    
    # Loop over years and countries
    for year in years:
        web_current_year = str(year)
        print(f"\n{colorama.Fore.YELLOW}=================== MEMPROSES TAHUN {year} ==================={colorama.Style.RESET_ALL}")
        
        categories_keys = list(selected_genres.keys())
        for idx, genre_name in enumerate(categories_keys):
            info = selected_genres[genre_name]
            web_current_genre = genre_name
            genre_queries = info["queries"]
            genre_artists = info["artists"]
            
            # Check year total collected songs (resumeable)
            collected_this_year = sum(1 for t in all_tracks if t['Tahun'] == year)
            year_limit = 50000 if unlimited_mode else max(total_target_songs // num_years, 1)
            
            if collected_this_year >= year_limit:
                print(f" -> Tahun {year} sudah lengkap ({collected_this_year}/{year_limit} lagu). Melewati sisa kategori untuk tahun ini...")
                break
                
            if unlimited_mode:
                active_genre_limit = 50000
            else:
                remaining_categories = len(categories_keys) - idx
                remaining_target_this_year = year_limit - collected_this_year
                active_genre_limit = max(remaining_target_this_year // remaining_categories, 1)
                
            print(f"\n -> Kategori: {colorama.Fore.CYAN}{genre_name}{colorama.Style.RESET_ALL} (Tahun {year}, Target Kategori Ini: {active_genre_limit} lagu)")
            
            seen_local = set()
            genre_tracks = []
            
            # Step A: Targeted Artist Searches via Deezer
            if genre_artists:
                print("    Mencari lagu dari artis populer (Deezer)...")
                active_artists = genre_artists  # Process all defined/custom artists
                
                for artist_name in tqdm(active_artists, desc="    Artis", unit="artis", leave=False):
                    if len(genre_tracks) >= active_genre_limit:
                        break
                    
                    # Strategy 1: Search artist top tracks via Artist ID
                    if artist_name not in artist_id_cache:
                        artist_data = deezer_search_artist(artist_name)
                        if artist_data:
                            artist_id_cache[artist_name] = artist_data.get('id')
                        else:
                            artist_id_cache[artist_name] = None
                    
                    a_id = artist_id_cache.get(artist_name)
                    
                    if a_id:
                        # Get top tracks (sorted by popularity automatically)
                        top_tracks = deezer_get_artist_top(a_id, limit=50)
                        for track in top_tracks:
                            if len(genre_tracks) >= active_genre_limit:
                                break
                            _add_deezer_track(track, genre_name, year)
                    
                    # Strategy 2: Also do a text search for this artist
                    if len(genre_tracks) < active_genre_limit:
                        search_results = deezer_search_tracks(artist_name, limit=25)
                        for track in search_results:
                            if len(genre_tracks) >= active_genre_limit:
                                break
                            _add_deezer_track(track, genre_name, year)
                    
                    time.sleep(0.25)  # Gentle rate limiting for Deezer
                
                print(f"    Artis -> {colorama.Fore.CYAN}{len(genre_tracks)} lagu ditemukan{colorama.Style.RESET_ALL}")
            
            # Step B: Broad Genre/Category Searches with pagination
            if len(genre_tracks) < active_genre_limit:
                remaining = active_genre_limit - len(genre_tracks)
                print(f"    Mencari lagu tambahan berdasarkan genre ({remaining} sisa kuota)...")
                
                for query_term in genre_queries:
                    if len(genre_tracks) >= active_genre_limit:
                        break
                    
                    # Paginate through Deezer search results for this query term (deeper search in unlimited mode)
                    max_search_index = 1000 if unlimited_mode else 250
                    for index in range(0, max_search_index, 50):
                        if len(genre_tracks) >= active_genre_limit:
                            break
                        
                        tracks = deezer_search_tracks(query_term, limit=50, index=index)
                        if not tracks:
                            break  # No more results
                        
                        for track in tracks:
                            if len(genre_tracks) >= active_genre_limit:
                                break
                            _add_deezer_track(track, genre_name, year)
                        
                        time.sleep(0.3)
                
                print(f"    Genre -> {colorama.Fore.CYAN}{len(genre_tracks)} lagu total{colorama.Style.RESET_ALL}")
            
            # Step C: Sort by Deezer Rank (popularity) and cap to active_genre_limit
            genre_tracks_sorted = sorted(genre_tracks, key=lambda x: x['Popularity'], reverse=True)
            genre_tracks_final = genre_tracks_sorted[:active_genre_limit]
            
            # Remove the temporary 'Popularity' column before final store
            new_finalized_tracks = []
            for gt in genre_tracks_final:
                gt_copy = dict(gt)
                gt_copy.pop('Popularity', None)
                all_tracks.append(gt_copy)
                new_finalized_tracks.append(gt_copy)
                
            # Append new finalized tracks to CSV immediately for resume checkpointing
            if new_finalized_tracks:
                try:
                    file_exists = os.path.exists(csv_path)
                    with open(csv_path, 'a', encoding='utf-8', newline='') as f:
                        writer = csv.DictWriter(f, fieldnames=['Nama Penyanyi', 'Judul Lagu', 'Kategori', 'Tahun'])
                        if not file_exists:
                            writer.writeheader()
                        for t in new_finalized_tracks:
                            writer.writerow(t)
                except Exception as e:
                    print(f" {colorama.Fore.RED}[Warning] Gagal menulis progress CSV: {e}{colorama.Style.RESET_ALL}")
                
            # Update web_collected_songs with actual final list under lock
            with web_songs_lock:
                web_collected_songs = list(all_tracks)
                
            print(f"    {colorama.Fore.GREEN}Sukses! Mengumpulkan {len(genre_tracks_final)} lagu populer teratas.{colorama.Style.RESET_ALL}")
            time.sleep(0.5) # Avoid hammering the API

    # Stop Web UI server active status
    web_running = False

    # 4. Save Outputs
    if not all_tracks:
        print(f"\n{colorama.Fore.RED} [Error] Tidak ada lagu populer yang berhasil dikumpulkan. Silakan coba rentang tahun lain.{colorama.Style.RESET_ALL}")
        sys.exit(1)
        
    # Write sorted CSV
    try:
        df = pd.DataFrame(all_tracks)
        df.sort_values(by=['Kategori', 'Tahun', 'Nama Penyanyi', 'Judul Lagu'], inplace=True, ignore_index=True)
        df.to_csv(csv_path, index=False, encoding='utf-8')
        print(f"\n -> Menyimpan file CSV Final: {colorama.Fore.GREEN}{csv_filename}{colorama.Style.RESET_ALL}")
    except Exception as e:
        print(f"{colorama.Fore.RED} [Error] Gagal menulis file CSV: {e}{colorama.Style.RESET_ALL}")
        
    # Compile to Sorted, styled Excel
    try:
        df = pd.DataFrame(all_tracks)
        df.sort_values(by=['Kategori', 'Tahun', 'Nama Penyanyi', 'Judul Lagu'], inplace=True, ignore_index=True)
        df.to_excel(xlsx_path, index=False)
        print(f" -> Menyimpan file Excel Final: {colorama.Fore.GREEN}{xlsx_filename}{colorama.Style.RESET_ALL}")
    except Exception as e:
        print(f"{colorama.Fore.RED} [Error] Gagal menulis file Excel: {e}{colorama.Style.RESET_ALL}")
        
    print(f"\n{colorama.Fore.GREEN}=========================================================={colorama.Style.RESET_ALL}")
    print(f"  SELESAI! Total mengumpulkan {colorama.Fore.WHITE}{len(all_tracks)} lagu populer{colorama.Style.RESET_ALL} dari Deezer.")
    print(f"  File siap digunakan: {colorama.Fore.CYAN}spotify_generator\\{xlsx_filename}{colorama.Style.RESET_ALL}")
    print(f"{colorama.Fore.GREEN}=========================================================={colorama.Style.RESET_ALL}\n")
    
    # Keep server running for a few minutes or print message
    print(f"  Dashboard Web UI tetap aktif di {colorama.Fore.CYAN}http://localhost:{server_port}{colorama.Style.RESET_ALL}")
    print("  Tekan sembarang tombol di terminal untuk menutup program...")

if __name__ == "__main__":
    main()
