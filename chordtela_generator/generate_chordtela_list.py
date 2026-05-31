import os
import sys
import json
import re
import csv
import urllib.request
import urllib.parse
import time
import random
import colorama
import pandas as pd
import threading
import queue
import http.server
import socketserver
import html
from html.parser import HTMLParser

colorama.init()

# Global variables for Web UI Dashboard (port 8002)
web_current_letter = ""
web_collected_songs = []
web_running = False
web_scraped_artists_count = 0
web_songs_lock = threading.Lock()
server_port = 8002

MAX_WORKERS = 6
worker_states = [{"artist": "Idle", "status": "Menunggu..."} for _ in range(MAX_WORKERS)]
worker_states_lock = threading.Lock()

# Lock definitions for safety
csv_write_lock = threading.Lock()
scraped_seen_lock = threading.Lock()
progress_write_lock = threading.Lock()

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chordtela Scraper Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #060913;
            --card-bg: rgba(15, 23, 42, 0.6);
            --border-color: rgba(0, 204, 0, 0.15);
            --primary: #00cc00;
            --primary-glow: rgba(0, 204, 0, 0.35);
            --secondary: #10b981;
            --text: #f1f5f9;
            --text-muted: #64748b;
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
                radial-gradient(circle at 10% 20%, rgba(0, 204, 0, 0.08) 0%, transparent 40%),
                radial-gradient(circle at 90% 80%, rgba(16, 185, 129, 0.08) 0%, transparent 40%);
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
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            padding-bottom: 1.5rem;
        }

        .logo {
            font-size: 1.8rem;
            font-weight: 800;
            background: linear-gradient(135deg, #00cc00, #10b981);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .status-badge {
            background: rgba(0, 204, 0, 0.1);
            color: var(--primary);
            padding: 0.5rem 1rem;
            border-radius: 50px;
            font-size: 0.9rem;
            font-weight: 600;
            border: 1px solid rgba(0, 204, 0, 0.2);
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
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }

        .card {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.5rem;
            backdrop-filter: blur(10px);
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
        }

        .card h3 {
            font-size: 0.85rem;
            text-transform: uppercase;
            color: var(--text-muted);
            margin-bottom: 0.5rem;
            font-weight: 600;
        }

        .card .val {
            font-size: 1.8rem;
            font-weight: 800;
            color: #fff;
        }

        .main-layout {
            display: grid;
            grid-template-columns: 2.2fr 1fr;
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
            max-height: 650px;
        }

        .table-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }

        .search-box {
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255, 255, 255, 0.08);
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
            border-bottom: 1px solid rgba(255,255,255,0.08);
            font-size: 0.9rem;
        }

        td {
            padding: 0.75rem 1rem;
            border-bottom: 1px solid rgba(255,255,255,0.02);
            font-size: 0.95rem;
        }

        .stat-sidebar {
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
        }

        .letter-stats-container {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.5rem;
            backdrop-filter: blur(10px);
        }

        .stat-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.6rem;
            padding-bottom: 0.6rem;
            border-bottom: 1px solid rgba(255,255,255,0.03);
        }

        .stat-name {
            font-weight: 600;
        }

        .stat-count {
            background: rgba(0, 204, 0, 0.1);
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
            <div class="logo">🎸 Chordtela Song Scraper Bot</div>
            <div class="status-badge" id="status-text">Menghubungkan...</div>
        </header>

        <div class="grid">
            <div class="card">
                <h3>Indeks Abjad</h3>
                <div class="val" id="stat-letter">-</div>
            </div>
            <div class="card">
                <h3>Penyanyi Selesai</h3>
                <div class="val" id="stat-artists-count">0</div>
            </div>
            <div class="card">
                <h3>Lagu Terkumpul</h3>
                <div class="val" id="stat-songs">0</div>
            </div>
        </div>

        <div class="grid" style="grid-template-columns: 1fr; margin-bottom: 2rem;">
            <div class="card">
                <h3>Status Worker Scraper (6 Threads Parallel)</h3>
                <div id="workers-wrapper" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-top: 1rem;">
                    <!-- Filled dynamically -->
                </div>
            </div>
        </div>

        <div class="main-layout">
            <div class="songs-table-container">
                <div class="table-header">
                    <h2>Lagu Terkumpul (Tanpa Duplikasi)</h2>
                    <input type="text" class="search-box" id="search-input" placeholder="Cari penyanyi atau judul...">
                </div>
                <div class="table-wrapper">
                    <table>
                        <thead>
                            <tr>
                                <th>Penyanyi</th>
                                <th>Judul Lagu</th>
                                <th>Sumber</th>
                                <th>Tautan</th>
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

            <div class="stat-sidebar">
                <div class="letter-stats-container">
                    <h2 style="margin-bottom: 1rem; font-size: 1.2rem;">Statistik Abjad</h2>
                    <div id="stats-wrapper">
                        <div style="color: var(--text-muted);">Belum ada data...</div>
                    </div>
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
                
                document.getElementById('status-text').innerText = data['running'] ? 'Sedang Scraping...' : 'Selesai';
                if (!data['running']) {
                    document.getElementById('status-text').style.boxShadow = 'none';
                    document.getElementById('status-text').style.background = 'rgba(255,255,255,0.05)';
                    document.getElementById('status-text').style.color = '#fff';
                    document.getElementById('status-text').style.animation = 'none';
                }
                
                document.getElementById('stat-letter').innerText = data['current_letter'] || '-';
                document.getElementById('stat-artists-count').innerText = data['scraped_artists_count'];
                document.getElementById('stat-songs').innerText = data['total_songs'];
                
                allSongs = data['songs'] || [];
                renderSongsTable();
                renderLetterStats(data['letter_stats']);
                renderWorkers(data['workers']);
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

            filtered.slice().reverse().slice(0, 100).forEach(s => {
                rowsHtml += `
                    <tr>
                        <td style="font-weight: 600; color: #fff;">${s['Nama Penyanyi']}</td>
                        <td>${s['Judul Lagu']}</td>
                        <td><span style="background: rgba(0,204,0,0.1); color: var(--primary); padding: 0.2rem 0.5rem; border-radius: 6px; font-size: 0.8rem; border: 1px solid rgba(0,204,0,0.2);">${s['Kategori/Genre']}</span></td>
                        <td><a href="${s['Tautan']}" target="_blank" style="font-size: 0.85rem; color: #00cc00;">Buka ↗</a></td>
                    </tr>
                `;
            });

            if (rowsHtml === '') {
                rowsHtml = '<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 2rem;">Tidak ada data lagu</td></tr>';
            }
            tbody.innerHTML = rowsHtml;
        }

        function renderLetterStats(stats) {
            let wrapper = document.getElementById('stats-wrapper');
            let html = '';
            for (let [cat, count] of Object.entries(stats || {})) {
                html += `
                    <div class="stat-row">
                        <span class="stat-name">Indeks ${cat}</span>
                        <span class="stat-count">${count} lagu</span>
                    </div>
                `;
            }
            if (html === '') {
                html = '<div style="color: var(--text-muted);">Belum ada data...</div>';
            }
            wrapper.innerHTML = html;
        }

        function renderWorkers(workers) {
            let wrapper = document.getElementById('workers-wrapper');
            let html = '';
            (workers || []).forEach((w, idx) => {
                let isScraping = w.status.includes('Scraping');
                let statusBg = isScraping ? 'rgba(0,204,0,0.1)' : 'rgba(255,255,255,0.04)';
                let statusColor = isScraping ? 'var(--primary)' : 'var(--text-muted)';
                let artistText = w.artist || 'Idle';
                
                html += `
                    <div style="background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05); padding: 1rem; border-radius: 12px; display: flex; flex-direction: column; gap: 0.35rem; overflow: hidden;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.2rem;">
                            <span style="font-size: 0.75rem; color: var(--text-muted); font-weight: 800;">THREAD ${idx + 1}</span>
                            <span style="font-size: 0.7rem; font-weight: 700; padding: 0.15rem 0.45rem; border-radius: 4px; background: ${statusBg}; color: ${statusColor}; text-transform: uppercase;">${w.status}</span>
                        </div>
                        <div style="font-size: 0.95rem; font-weight: 600; color: #fff; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${artistText}">
                            ${artistText}
                        </div>
                    </div>
                `;
            });
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
        global web_current_letter, web_collected_songs, web_running, web_scraped_artists_count
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
                
            # Group stats by letter
            letter_stats = {}
            for s in songs_copy:
                cat = s.get('Kategori/Genre', 'Lainnya')
                letter_stats[cat] = letter_stats.get(cat, 0) + 1
                
            with worker_states_lock:
                workers_copy = list(worker_states)
                
            data = {
                'current_letter': web_current_letter,
                'total_songs': len(songs_copy),
                'running': web_running,
                'scraped_artists_count': web_scraped_artists_count,
                'songs': songs_copy,
                'letter_stats': letter_stats,
                'workers': workers_copy
            }
            self.wfile.write(json.dumps(data).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

def start_web_ui_server(port=8002):
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

# ============================================================
#  HTML PARSERS FOR CHORDTELA
# ============================================================

class ArtistIndexParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.artist_links = []
        self.in_a = False
        self.current_attrs = {}

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.in_a = True
            self.current_attrs = dict(attrs)

    def handle_endtag(self, tag):
        if tag == "a":
            self.in_a = False

    def handle_data(self, data):
        if self.in_a:
            href = self.current_attrs.get("href", "")
            if "/chord/" in href and not href.endswith(".html") and not "/page/" in href:
                cleaned_href = href.strip()
                if not any(x in cleaned_href for x in ["chord-gitar-", "buku-tamu", "request-chord", "tool-transpose", "daftar-isi"]):
                    if cleaned_href.startswith("/"):
                        cleaned_href = "https://www.chordtela.com" + cleaned_href
                    artist_name = data.strip()
                    if artist_name and (cleaned_href, artist_name) not in self.artist_links:
                        self.artist_links.append((cleaned_href, artist_name))

class ArtistPageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.song_links = []
        self.in_a = False
        self.current_attrs = {}
        self.a_text = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.in_a = True
            self.a_text = []
            self.current_attrs = dict(attrs)

    def handle_endtag(self, tag):
        if tag == "a" and self.in_a:
            text = "".join(self.a_text).strip()
            href = self.current_attrs.get("href", "")
            if href.endswith(".html"):
                if href.startswith("/"):
                    href = "https://www.chordtela.com" + href
                if (href, text) not in self.song_links:
                    self.song_links.append((href, text))
            self.in_a = False

    def handle_data(self, data):
        if self.in_a:
            self.a_text.append(data)

# ============================================================
#  HTTP UTILITIES WITH EVASION
# ============================================================

def fetch_html(url, worker_id=None):
    """Fetch HTML content with customized headers, timeout, and back-off retries."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7',
        'Connection': 'keep-alive',
        'Referer': 'https://www.chordtela.com/'
    }
    
    max_retries = 3
    base_sleep = 30 # Back off for 30s if rate limited
    
    for attempt in range(max_retries):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                return response.read().decode('utf-8', errors='ignore')
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                t_pref = f"[Thread {worker_id+1}] " if worker_id is not None else ""
                print(f"      {colorama.Fore.YELLOW}{t_pref}[Evasion] Terblokir (HTTP {e.code}). Berhenti sejenak {base_sleep} detik...{colorama.Style.RESET_ALL}")
                if worker_id is not None:
                    with worker_states_lock:
                        worker_states[worker_id]["status"] = "Terblokir"
                time.sleep(base_sleep)
                base_sleep *= 2
                continue
            else:
                return None
        except Exception:
            time.sleep(2)
    return None

# ============================================================
#  CLEANING & PARSING UTILITIES
# ============================================================

def clean_song_text(text):
    text = html.unescape(text)
    # Remove bracketed details
    text = re.sub(r'[\(\[]\s*(chord|kunci gitar|chord dasar|lirik dan chord|lirik|cover|feat)[^\]\)]*[\)\]]', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^(chord|kunci gitar|lirik)\s+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+(chord|kunci gitar|lirik)$', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def parse_song_text(text, current_artist_name=""):
    cleaned = clean_song_text(text)
    parts = re.split(r'\s+-\s+|\s+–\s+|\s+—\s+', cleaned, maxsplit=1)
    if len(parts) == 2:
        part1 = parts[0].strip()
        part2 = parts[1].strip()
        
        if current_artist_name:
            def clean_for_match(s):
                return re.sub(r'[^a-z0-9\s]', '', s.lower()).strip()
                
            clean_artist = clean_for_match(current_artist_name)
            clean_part1 = clean_for_match(part1)
            clean_part2 = clean_for_match(part2)
            
            def has_artist_words(part_clean, artist_clean):
                if not artist_clean or not part_clean:
                    return False
                words_artist = artist_clean.split()
                words_part = part_clean.split()
                if not words_artist or not words_part:
                    return False
                n_artist = len(words_artist)
                n_part = len(words_part)
                for i in range(n_part - n_artist + 1):
                    if words_part[i:i+n_artist] == words_artist:
                        return True
                return False
                
            match1 = has_artist_words(clean_part1, clean_artist)
            match2 = has_artist_words(clean_part2, clean_artist)
            
            if match1 and match2:
                exact1 = (clean_part1 == clean_artist)
                exact2 = (clean_part2 == clean_artist)
                if exact1 and not exact2:
                    swap = False
                elif exact2 and not exact1:
                    swap = True
                else:
                    len_art = len(clean_artist.split())
                    diff1 = abs(len(clean_part1.split()) - len_art)
                    diff2 = abs(len(clean_part2.split()) - len_art)
                    swap = (diff2 < diff1)
            elif match2 and not match1:
                swap = True
            else:
                swap = False
                
            if swap:
                artist = part2
                title = part1
            else:
                artist = part1
                title = part2
        else:
            artist = part1
            title = part2
    else:
        artist = "Unknown"
        title = cleaned
    return artist, title

# ============================================================
#  WORKER THREAD IMPLEMENTATION
# ============================================================

def scraper_worker(worker_id, q, excel_seen, scraped_seen, processed_artists, csv_path, progress_json_path):
    global web_scraped_artists_count
    
    while not q.empty():
        try:
            artist_url, artist_name, letter_name = q.get_nowait()
        except queue.Empty:
            break
            
        with worker_states_lock:
            worker_states[worker_id] = {"artist": artist_name, "status": "Scraping"}
            
        html_content = fetch_html(artist_url, worker_id)
        if not html_content:
            with worker_states_lock:
                worker_states[worker_id] = {"artist": artist_name, "status": "Gagal"}
            q.task_done()
            time.sleep(1)
            continue
            
        parser = ArtistPageParser()
        parser.feed(html_content)
        
        new_artist_songs = []
        for song_url, song_title_text in parser.song_links:
            parsed_artist, parsed_title = parse_song_text(song_title_text, current_artist_name=artist_name)
            
            if parsed_artist == "Unknown" or not parsed_artist:
                parsed_artist = artist_name
                
            dup_key = f"{parsed_artist.lower().strip()} - {parsed_title.lower().strip()}"
            
            # Thread-safe duplicate checking
            with scraped_seen_lock:
                if dup_key in excel_seen or dup_key in scraped_seen:
                    continue
                scraped_seen.add(dup_key)
                
            new_artist_songs.append({
                'Nama Penyanyi': parsed_artist,
                'Judul Lagu': parsed_title,
                'Kategori/Genre': letter_name,
                'Tautan': song_url
            })
            
        # Write to CSV in a thread-safe manner
        if new_artist_songs:
            with csv_write_lock:
                file_exists = os.path.exists(csv_path)
                try:
                    with open(csv_path, 'a', encoding='utf-8', newline='') as f:
                        writer = csv.DictWriter(f, fieldnames=['Nama Penyanyi', 'Judul Lagu', 'Tautan'], extrasaction='ignore')
                        if not file_exists:
                            writer.writeheader()
                        for t in new_artist_songs:
                            writer.writerow(t)
                    
                    # Update global display variables
                    with web_songs_lock:
                        web_collected_songs.extend(new_artist_songs)
                except Exception as e:
                    print(f"     [Thread {worker_id+1}] {colorama.Fore.RED}[Warning] Gagal menulis ke CSV: {e}{colorama.Style.RESET_ALL}")
                    
            print(f"     [Thread {worker_id+1}] {colorama.Fore.GREEN}+ {len(new_artist_songs)} lagu baru dari {artist_name}{colorama.Style.RESET_ALL}")
            
        # Update progress tracking JSON safely
        with progress_write_lock:
            processed_artists.add(artist_url)
            web_scraped_artists_count = len(processed_artists)
            try:
                with open(progress_json_path, 'w', encoding='utf-8') as f:
                    json.dump({'processed_artists': list(processed_artists)}, f, indent=4)
            except Exception:
                pass
                
        # Evasion rate limiting delay
        with worker_states_lock:
            worker_states[worker_id] = {"artist": "Idle", "status": "Delay"}
        time.sleep(random.uniform(2.5, 5.0))
        
        with worker_states_lock:
            worker_states[worker_id] = {"artist": "Idle", "status": "Idle"}
            
        q.task_done()

# ============================================================
#  MAIN scraper ENTRYPOINT
# ============================================================

INDEX_PAGES = [
    ("A-B", "https://www.chordtela.com/chord-gitar-a-b"),
    ("C-D", "https://www.chordtela.com/chord-gitar-c-d"),
    ("E-F", "https://www.chordtela.com/chord-gitar-e-f"),
    ("G-H", "https://www.chordtela.com/chord-gitar-g-h"),
    ("I-J", "https://www.chordtela.com/chord-gitar-i-j"),
    ("K-L", "https://www.chordtela.com/chord-gitar-k-l"),
    ("M-N", "https://www.chordtela.com/chord-gitar-m-n"),
    ("O-P", "https://www.chordtela.com/chord-gitar-o-p"),
    ("Q-R", "https://www.chordtela.com/chord-gitar-q-r"),
    ("S-T", "https://www.chordtela.com/chord-gitar-s-t"),
    ("U-V", "https://www.chordtela.com/chord-gitar-u-v"),
    ("W-X", "https://www.chordtela.com/chord-gitar-w-x"),
    ("Y-Z", "https://www.chordtela.com/chord-gitar-y-z"),
    ("0-9", "https://www.chordtela.com/chord-gitar-0-9")
]

def get_category_from_artist(artist_name):
    if not artist_name:
        return "Lainnya"
    first_char = artist_name[0].upper()
    if first_char.isdigit():
        return "0-9"
    for cat_range in ["A-B", "C-D", "E-F", "G-H", "I-J", "K-L", "M-N", "O-P", "Q-R", "S-T", "U-V", "W-X", "Y-Z"]:
        start, end = cat_range.split("-")
        if start <= first_char <= end:
            return cat_range
    return "Lainnya"

def main():
    global web_current_letter, web_collected_songs, web_running, web_scraped_artists_count
    
    proj_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(proj_dir)
    excel_playlist_path = os.path.join(parent_dir, "Karaoke_Playlist_Clean.xlsx")
    
    csv_path = os.path.join(proj_dir, "list_lagu_chordtela.csv")
    xlsx_path = os.path.join(proj_dir, "list_lagu_chordtela.xlsx")
    progress_json_path = os.path.join(proj_dir, "list_lagu_chordtela_progress.json")
    
    print(f"{colorama.Fore.GREEN}=========================================================={colorama.Style.RESET_ALL}")
    print(f"         CHORDTELA SONG LIST GENERATOR BOT (6 THREADS)    ")
    print(f"{colorama.Fore.GREEN}=========================================================={colorama.Style.RESET_ALL}")
    
    # 1. Load Karaoke_Playlist_Clean.xlsx blacklist
    excel_seen = set()
    if os.path.exists(excel_playlist_path):
        print(f" Memuat basis data riwayat dari Karaoke_Playlist_Clean.xlsx...")
        try:
            df_playlist = pd.read_excel(excel_playlist_path)
            for idx, row in df_playlist.iterrows():
                artist_raw = str(row.get('Nama Penyanyi', '')).lower().strip()
                title_raw = str(row.get('Judul Lagu', '')).lower().strip()
                if artist_raw and title_raw:
                    excel_seen.add(f"{artist_raw} - {title_raw}")
                    excel_seen.add(f"{title_raw} - {artist_raw}")
            print(f" -> {colorama.Fore.GREEN}Berhasil memuat {len(excel_seen) // 2} lagu yang sudah diunduh.{colorama.Style.RESET_ALL}")
        except Exception as e:
            print(f" {colorama.Fore.RED}[Warning] Gagal membaca Excel playlist: {e}{colorama.Style.RESET_ALL}")
    else:
        print(f" {colorama.Fore.YELLOW}[Warning] Karaoke_Playlist_Clean.xlsx tidak ditemukan. Scraping tanpa filter riwayat.{colorama.Style.RESET_ALL}")
        
    # 2. Check for resume data
    processed_artists = set()
    if os.path.exists(progress_json_path):
        try:
            with open(progress_json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                processed_artists = set(data.get('processed_artists', []))
            print(f" -> {colorama.Fore.GREEN}Berhasil memuat status resume: {len(processed_artists)} penyanyi telah selesai diproses.{colorama.Style.RESET_ALL}")
        except Exception as e:
            print(f" {colorama.Fore.RED}[Warning] Gagal membaca progress JSON: {e}{colorama.Style.RESET_ALL}")
            
    # Load existing scraped items from CSV
    all_tracks = []
    scraped_seen = set()
    if os.path.exists(csv_path):
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    artist = row.get('Nama Penyanyi', '')
                    title = row.get('Judul Lagu', '')
                    category = row.get('Kategori/Genre')
                    if not category:
                        category = get_category_from_artist(artist)
                    tautan = row.get('Tautan', '')
                    track_item = {
                        'Nama Penyanyi': artist,
                        'Judul Lagu': title,
                        'Kategori/Genre': category,
                        'Tautan': tautan
                    }
                    all_tracks.append(track_item)
                    scraped_seen.add(f"{artist.lower().strip()} - {title.lower().strip()}")
            print(f" -> {colorama.Fore.GREEN}Berhasil memuat {len(all_tracks)} lagu dari progress CSV sebelumnya.{colorama.Style.RESET_ALL}")
        except Exception as e:
            print(f" {colorama.Fore.RED}[Warning] Gagal membaca progress CSV: {e}{colorama.Style.RESET_ALL}")
            
    web_collected_songs = list(all_tracks)
    web_scraped_artists_count = len(processed_artists)
    
    # 3. Start live Web UI dashboard on port 8002
    web_running = True
    start_web_ui_server(port=8002)
    print(f"  Live Web UI Dashboard: {colorama.Fore.CYAN}http://localhost:{server_port}{colorama.Style.RESET_ALL}")
    print(f"{colorama.Fore.GREEN}----------------------------------------------------------{colorama.Style.RESET_ALL}")
    print(" Menghubungkan ke Chordtela untuk mengunduh semua daftar artis...")
    
    # 4. Crawl index pages to get ALL artist links
    all_artists_list = [] # List of tuples: (artist_url, artist_name, letter_name)
    
    for letter_name, index_url in INDEX_PAGES:
        web_current_letter = letter_name
        print(f"  Mendapatkan daftar artis indeks abjad: {colorama.Fore.CYAN}{letter_name}{colorama.Style.RESET_ALL}")
        
        html_index = fetch_html(index_url)
        if not html_index:
            print(f"  {colorama.Fore.RED}[Warning] Gagal mengunduh indeks abjad {letter_name}. Melewati...{colorama.Style.RESET_ALL}")
            continue
            
        parser_idx = ArtistIndexParser()
        parser_idx.feed(html_index)
        
        for url, name in parser_idx.artist_links:
            # Exclude if already processed
            if url not in processed_artists:
                all_artists_list.append((url, name, letter_name))
        
        time.sleep(0.5) # Evasion delay between index pages
        
    print(f"\n Total artis baru yang perlu di-scrape: {colorama.Fore.GREEN}{len(all_artists_list)}{colorama.Style.RESET_ALL} (dari total {len(all_artists_list) + len(processed_artists)} artis)")
    
    if not all_artists_list:
        print(f"\n{colorama.Fore.GREEN} Semua artis dari A-Z & 0-9 sudah selesai diproses!{colorama.Style.RESET_ALL}")
    else:
        # 5. Populate scraping queue
        artist_queue = queue.Queue()
        for item in all_artists_list:
            artist_queue.put(item)
            
        # Start 6 worker threads
        print(f" Memulai {MAX_WORKERS} worker threads parallel dengan proteksi rate limit...")
        threads = []
        for i in range(MAX_WORKERS):
            t = threading.Thread(
                target=scraper_worker,
                args=(i, artist_queue, excel_seen, scraped_seen, processed_artists, csv_path, progress_json_path),
                daemon=True
            )
            t.start()
            threads.append(t)
            
        # Wait for all queue items to be processed
        try:
            while not artist_queue.empty():
                time.sleep(1)
            # Wait for all active threads to finish their current items
            for t in threads:
                t.join(timeout=1.0)
        except KeyboardInterrupt:
            print(f"\n{colorama.Fore.YELLOW} [Info] Deteksi interupsi (Ctrl+C). Menyimpan progress dan bersiap keluar...{colorama.Style.RESET_ALL}")
            
    # 6. Conversion to XLSX Final upon completion/interruption
    web_running = False
    with worker_states_lock:
        for idx in range(MAX_WORKERS):
            worker_states[idx] = {"artist": "Idle", "status": "Selesai"}
            
    print(f"\n{colorama.Fore.GREEN}=========================================================={colorama.Style.RESET_ALL}")
    print(f" Menyimpan berkas Excel final...")
    
    if os.path.exists(csv_path):
        try:
            df_final = pd.read_csv(csv_path)
            # Sort by artist
            df_final.sort_values(by=['Nama Penyanyi', 'Judul Lagu'], inplace=True, ignore_index=True)
            df_final.to_excel(xlsx_path, index=False)
            print(f" -> {colorama.Fore.GREEN}Berkas Excel berhasil disimpan: {xlsx_path}{colorama.Style.RESET_ALL}")
        except Exception as e:
            print(f" {colorama.Fore.RED}[Error] Gagal mengonversi CSV ke Excel: {e}{colorama.Style.RESET_ALL}")
    else:
        print(f" {colorama.Fore.YELLOW}[Warning] Berkas CSV tidak ditemukan.{colorama.Style.RESET_ALL}")
        
    print(f"{colorama.Fore.GREEN}=========================================================={colorama.Style.RESET_ALL}\n")
    print(f" Dashboard Web UI tetap aktif di {colorama.Fore.CYAN}http://localhost:{server_port}{colorama.Style.RESET_ALL}")
    print(" Tekan Ctrl+C di terminal ini untuk menutup program.")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n Program ditutup.")

if __name__ == "__main__":
    main()
