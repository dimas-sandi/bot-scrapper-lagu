import os
import sys
import json
import re
import csv
import argparse
import time
import threading
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
import colorama
import pandas as pd
import yt_dlp
import http.server
import socketserver

# Add current directory to sys.path for list_generator loading
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import list_generator

colorama.init()

# Global variables for TUI and Thread-safe updates
worker_states = []
worker_states_lock = threading.Lock()
excel_write_lock = threading.Lock()

# TUI states
completed_count = 0
processed_count = 0
failed_tasks = []
total_tasks = 0
existing_df = None
running = False
first_draw = True
years = []
output_path = ""
limit = 250
completed_steps = []
seen_songs = set()
completed_songs = set()
server_port = 8000
run_start_time = time.time()
initial_completed_count = 0

# HTML Dashboard Template for Real-time Web UI
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Live Playlist Generator Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0b0f19;
            --card-bg: rgba(20, 30, 55, 0.5);
            --border-color: rgba(255, 255, 255, 0.08);
            --primary: #8b5cf6;
            --primary-glow: rgba(139, 92, 246, 0.4);
            --secondary: #3b82f6;
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
                radial-gradient(circle at 10% 20%, rgba(59, 130, 246, 0.1) 0%, transparent 40%),
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

        h1 {
            font-size: 2.2rem;
            font-weight: 800;
            background: linear-gradient(135deg, #3b82f6, #8b5cf6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .server-badge {
            background: rgba(16, 185, 129, 0.15);
            color: var(--success);
            padding: 0.5rem 1rem;
            border-radius: 9999px;
            font-weight: 600;
            font-size: 0.9rem;
            border: 1px solid rgba(16, 185, 129, 0.3);
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .server-badge::before {
            content: '';
            display: inline-block;
            width: 8px;
            height: 8px;
            background-color: var(--success);
            border-radius: 50%;
            box-shadow: 0 0 8px var(--success);
            animation: pulse 1.5s infinite;
        }

        @keyframes pulse {
            0% { transform: scale(0.9); opacity: 0.6; }
            50% { transform: scale(1.2); opacity: 1; }
            100% { transform: scale(0.9); opacity: 0.6; }
        }

        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2.5rem;
        }

        .stat-card {
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.5rem;
            display: flex;
            flex-direction: column;
            position: relative;
            overflow: hidden;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
        }

        .stat-card::after {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 4px; height: 100%;
            background: var(--primary);
        }

        .stat-card.blue::after { background: var(--secondary); }
        .stat-card.success::after { background: var(--success); }
        .stat-card.danger::after { background: var(--danger); }

        .stat-label {
            font-size: 0.9rem;
            color: var(--text-muted);
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.5rem;
        }

        .stat-value {
            font-size: 2.2rem;
            font-weight: 800;
            line-height: 1.2;
        }

        /* Progress section */
        .progress-section {
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border-color);
            border-radius: 20px;
            padding: 2rem;
            margin-bottom: 2.5rem;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
        }

        .progress-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }

        .progress-title {
            font-size: 1.2rem;
            font-weight: 600;
        }

        .progress-bar-container {
            width: 100%;
            height: 12px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 9999px;
            overflow: hidden;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }

        .progress-bar-fill {
            height: 100%;
            width: 0%;
            background: linear-gradient(90deg, var(--secondary), var(--primary));
            border-radius: 9999px;
            transition: width 0.5s cubic-bezier(0.4, 0, 0.2, 1);
            box-shadow: 0 0 10px var(--primary-glow);
        }

        /* Workers Grid */
        .workers-title {
            font-size: 1.4rem;
            font-weight: 700;
            margin-bottom: 1.2rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .workers-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2.5rem;
        }

        .worker-card {
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.2rem;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2);
            transition: all 0.3s ease;
            position: relative;
        }

        .worker-card:hover {
            transform: translateY(-4px);
            border-color: rgba(139, 92, 246, 0.3);
            box-shadow: 0 12px 40px 0 rgba(139, 92, 246, 0.15);
        }

        .worker-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.8rem;
        }

        .worker-name {
            font-weight: 700;
            font-size: 1rem;
            color: var(--text);
        }

        .worker-badge-status {
            font-size: 0.8rem;
            padding: 0.25rem 0.6rem;
            border-radius: 9999px;
            font-weight: 600;
            text-transform: uppercase;
        }

        .worker-status-idle { background: rgba(156, 163, 175, 0.15); color: var(--text-muted); border: 1px solid rgba(156, 163, 175, 0.3); }
        .worker-status-scrape { background: rgba(59, 130, 246, 0.15); color: var(--secondary); border: 1px solid rgba(59, 130, 246, 0.3); }
        .worker-status-target { background: rgba(236, 72, 153, 0.15); color: #ec4899; border: 1px solid rgba(236, 72, 153, 0.3); }
        .worker-status-general { background: rgba(139, 92, 246, 0.15); color: #a78bfa; border: 1px solid rgba(139, 92, 246, 0.3); }

        .worker-task {
            font-size: 0.9rem;
            color: var(--text-muted);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            margin-top: 0.25rem;
        }

        /* Two columns details */
        .details-section {
            display: grid;
            grid-template-columns: 1fr 320px;
            gap: 2rem;
        }

        @media (max-width: 900px) {
            .details-section {
                grid-template-columns: 1fr;
            }
        }

        /* Song Table Card */
        .table-card {
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border-color);
            border-radius: 20px;
            padding: 1.5rem;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
            display: flex;
            flex-direction: column;
            min-height: 500px;
        }

        .table-header-container {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.2rem;
            flex-wrap: wrap;
            gap: 1rem;
        }

        .table-title {
            font-size: 1.3rem;
            font-weight: 700;
        }

        .search-box {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border-color);
            padding: 0.6rem 1.2rem;
            border-radius: 12px;
            color: var(--text);
            font-family: inherit;
            outline: none;
            width: 280px;
            transition: all 0.3s ease;
        }

        .search-box:focus {
            border-color: var(--primary);
            box-shadow: 0 0 10px var(--primary-glow);
            background: rgba(255, 255, 255, 0.08);
        }

        .table-wrapper {
            overflow-x: auto;
            flex-grow: 1;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
        }

        th {
            padding: 1rem;
            font-size: 0.9rem;
            color: var(--text-muted);
            font-weight: 600;
            text-transform: uppercase;
            border-bottom: 1px solid var(--border-color);
        }

        td {
            padding: 1rem;
            font-size: 0.95rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.03);
        }

        tr:hover td {
            background: rgba(255, 255, 255, 0.02);
        }

        /* Sidebar stats */
        .genres-card {
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border-color);
            border-radius: 20px;
            padding: 1.5rem;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
            align-self: start;
        }

        .genres-title {
            font-size: 1.2rem;
            font-weight: 700;
            margin-bottom: 1.2rem;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 0.8rem;
        }

        .genre-row {
            margin-bottom: 1rem;
        }

        .genre-meta {
            display: flex;
            justify-content: space-between;
            font-size: 0.9rem;
            margin-bottom: 0.35rem;
        }

        .genre-bar-bg {
            height: 6px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 9999px;
            overflow: hidden;
        }

        .genre-bar-fill {
            height: 100%;
            background: var(--secondary);
            border-radius: 9999px;
            width: 0%;
            transition: width 0.5s ease;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>KARAOKE GENERATOR</h1>
                <p style="color: var(--text-muted); font-size: 0.95rem; margin-top: 0.2rem;">Live Dashboard Pemantauan Lagu</p>
            </div>
            <div class="server-badge">Live Syncing</div>
        </header>

        <!-- Stats Grid -->
        <div class="stats-grid">
            <div class="stat-card blue">
                <span class="stat-label">Total Lagu Terkumpul</span>
                <span class="stat-value" id="stat-total-songs">0</span>
            </div>
            <div class="stat-card">
                <span class="stat-label">Tugas Sukses</span>
                <span class="stat-value" id="stat-success-tasks" style="color: var(--success);">0</span>
            </div>
            <div class="stat-card danger">
                <span class="stat-label">Tugas Gagal / Limit</span>
                <span class="stat-value" id="stat-failed-tasks" style="color: var(--danger);">0</span>
            </div>
            <div class="stat-card success">
                <span class="stat-label">Total Tugas</span>
                <span class="stat-value" id="stat-total-tasks">0</span>
            </div>
        </div>

        <!-- Progress Section -->
        <div class="progress-section">
            <div class="progress-header">
                <span class="progress-title">Progres Scraping Playlist <span style="font-size: 0.95rem; color: var(--warning); margin-left: 1rem;" id="progress-eta">(Estimasi Sisa: Menghitung...)</span></span>
                <span class="progress-title" id="progress-text">0% (0/0 Tugas)</span>
            </div>
            <div class="progress-bar-container">
                <div class="progress-bar-fill" id="progress-bar"></div>
            </div>
        </div>

        <!-- Workers Status -->
        <div class="workers-title">
            <span>Status Worker (Real-time)</span>
        </div>
        <div class="workers-grid" id="workers-container">
            <!-- Dynamic worker cards -->
        </div>

        <!-- Details Section -->
        <div class="details-section">
            <!-- Song Table -->
            <div class="table-card">
                <div class="table-header-container">
                    <span class="table-title">Daftar Lagu Baru (Terbaru)</span>
                    <input type="text" class="search-box" id="search-input" placeholder="Cari penyanyi atau judul lagu...">
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
                            <!-- Dynamic rows -->
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Genres summary -->
            <div class="genres-card">
                <div class="genres-title">Ringkasan per Kategori</div>
                <div id="genres-container">
                    <!-- Dynamic genre summary bars -->
                </div>
            </div>
        </div>
    </div>

    <script>
        let allSongs = [];
        
        function updateDashboard() {
            fetch('/data')
                .then(response => response.json())
                .then(data => {
                    // Update stats
                    document.getElementById('stat-total-songs').textContent = data.total_songs;
                    document.getElementById('stat-success-tasks').textContent = data.completed_count;
                    document.getElementById('stat-failed-tasks').textContent = data.failed_count;
                    document.getElementById('stat-total-tasks').textContent = data.total_tasks;

                    // Update Progress
                    let total = data.total_tasks || 1;
                    let processed = data.processed_count || 0;
                    let percent = Math.round((processed / total) * 100);
                    document.getElementById('progress-bar').style.width = percent + '%';
                    document.getElementById('progress-text').textContent = percent + '% (' + processed + '/' + total + ' Tugas)';
                    document.getElementById('progress-eta').textContent = '(Estimasi Sisa: ' + (data.eta || 'Menghitung...') + ')';

                    // Update Workers
                    let workersHtml = '';
                    data.workers.forEach((w, index) => {
                        let statusClass = 'worker-status-idle';
                        let statusText = 'Idle';
                        if (w.status === 'Web Scraping') {
                            statusClass = 'worker-status-scrape';
                            statusText = 'Web Scrape';
                        } else if (w.status === 'Target Artist YT') {
                            statusClass = 'worker-status-target';
                            statusText = 'Target YT';
                        } else if (w.status === 'General YT Search') {
                            statusClass = 'worker-status-general';
                            statusText = 'General YT';
                        }

                        workersHtml += `
                            <div class="worker-card">
                                <div class="worker-header">
                                    <span class="worker-name">Worker ${index + 1}</span>
                                    <span class="worker-badge-status ${statusClass}">${statusText}</span>
                                </div>
                                <div class="worker-task">${w.task ? w.task : 'Menunggu antrean...'}</div>
                            </div>
                        `;
                    });
                    document.getElementById('workers-container').innerHTML = workersHtml;

                    // Save songs list
                    allSongs = data.songs || [];
                    renderSongsTable();

                    // Render Genre stats
                    let maxCount = 0;
                    Object.values(data.genre_stats).forEach(c => {
                        if (c > maxCount) maxCount = c;
                    });

                    let genresHtml = '';
                    Object.entries(data.genre_stats).sort((a,b) => b[1] - a[1]).forEach(([genre, count]) => {
                        let pct = maxCount > 0 ? Math.round((count / maxCount) * 100) : 0;
                        genresHtml += `
                            <div class="genre-row">
                                <div class="genre-meta">
                                    <span style="font-weight: 600;">${genre}</span>
                                    <span style="color: var(--text-muted);">${count} lagu</span>
                                </div>
                                <div class="genre-bar-bg">
                                    <div class="genre-bar-fill" style="width: ${pct}%;"></div>
                                </div>
                            </div>
                        `;
                    });
                    if (genresHtml === '') {
                        genresHtml = '<p style="color: var(--text-muted); font-size: 0.9rem; text-align: center;">Belum ada data</p>';
                    }
                    document.getElementById('genres-container').innerHTML = genresHtml;
                })
                .catch(err => console.error('Error fetching stats:', err));
        }

        function renderSongsTable() {
            let searchVal = document.getElementById('search-input').value.toLowerCase();
            let tbody = document.getElementById('songs-table-body');
            let rowsHtml = '';
            
            // Filter songs
            let filtered = allSongs.filter(s => {
                let penyanyi = (s['Nama Penyanyi'] || '').toLowerCase();
                let judul = (s['Judul Lagu'] || '').toLowerCase();
                return penyanyi.includes(searchVal) || judul.includes(searchVal);
            });

            // Display in reverse order (newest first)
            filtered.slice().reverse().forEach(s => {
                rowsHtml += `
                    <tr>
                        <td style="font-weight: 600; color: #fff;">${s['Nama Penyanyi']}</td>
                        <td>${s['Judul Lagu']}</td>
                        <td><span style="background: rgba(59,130,246,0.1); color: var(--secondary); padding: 0.2rem 0.5rem; border-radius: 6px; font-size: 0.8rem; border: 1px solid rgba(59,130,246,0.2);">${s['Kategori']}</span></td>
                        <td style="color: var(--text-muted);">${s['Tahun']}</td>
                    </tr>
                `;
            });

            if (rowsHtml === '') {
                rowsHtml = '<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 2rem;">Tidak ada data lagu</td></tr>';
            }
            tbody.innerHTML = rowsHtml;
        }

        document.getElementById('search-input').addEventListener('input', renderSongsTable);

        // Initial and periodic update
        updateDashboard();
        setInterval(updateDashboard, 1500);
    </script>
</body>
</html>
"""

class WebUIRequestHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass # Suppress standard log output to keep console tidy
        
    def do_GET(self):
        global output_path, total_tasks, completed_count, processed_count, failed_tasks, worker_states, run_start_time, initial_completed_count
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode('utf-8'))
        elif self.path == '/data':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            # Read CSV on the fly
            songs_list = []
            csv_path = output_path.replace('.xlsx', '.csv')
            if os.path.exists(csv_path):
                try:
                    # Thread-safe reading
                    with excel_write_lock:
                        df = pd.read_csv(csv_path)
                    # Convert to list of dicts, fill NaNs
                    df = df.fillna('')
                    songs_list = df.to_dict(orient='records')
                except:
                    pass
            
            # Group stats
            genre_stats = {}
            for s in songs_list:
                cat = s.get('Kategori', 'Lainnya')
                genre_stats[cat] = genre_stats.get(cat, 0) + 1
                
            # Build TUI worker stats copy
            with worker_states_lock:
                workers_copy = json.loads(json.dumps(worker_states))
                
            # Calculate dynamic ETA
            completed_this_run = processed_count - initial_completed_count
            if completed_this_run > 0:
                elapsed = time.time() - run_start_time
                time_per_task = elapsed / completed_this_run
                rem_tasks = total_tasks - processed_count
                eta_seconds = time_per_task * rem_tasks
                eta_str = format_duration(eta_seconds)
            else:
                eta_str = "Menghitung..."
                
            data = {
                'total_tasks': total_tasks,
                'completed_count': completed_count,
                'processed_count': processed_count,
                'failed_count': len(failed_tasks),
                'total_songs': len(songs_list),
                'workers': workers_copy,
                'songs': songs_list, # Send all songs so client can search locally
                'genre_stats': genre_stats,
                'eta': eta_str
            }
            self.wfile.write(json.dumps(data).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

def start_web_ui_server(port=8000):
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
            # Try next port
            server_port += 1
            if server_port > 8080:
                break

def format_duration(seconds):
    if seconds < 0:
        return "0s"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}j {m}m {s}s"
    elif m > 0:
        return f"{m}m {s}s"
    else:
        return f"{s}s"

def log_error(msg):
    proj_dir = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(proj_dir, "generator_error.log")
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {msg}\n")
    except:
        pass

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

def save_generator_state(state_path, state_data):
    tmp_path = state_path + ".tmp"
    try:
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(state_data, f, indent=2)
        os.replace(tmp_path, state_path)
    except:
        if os.path.exists(tmp_path):
            try: os.remove(tmp_path)
            except: pass

def write_resume_bat(proj_dir):
    bat_path = os.path.join(proj_dir, "resume_generator.bat")
    content = """@echo off
title YouTube Karaoke - Resume Playlist Generator
cd /d "%~dp0"
..\\python_embed\\python.exe generate_list.py --resume
echo.
echo Proses resume selesai atau dihentikan.
pause
"""
    try:
        with open(bat_path, 'w', encoding='utf-8') as f:
            f.write(content)
    except:
        pass

def cleanup_state_files(proj_dir, state_path):
    bat_path = os.path.join(proj_dir, "resume_generator.bat")
    if os.path.exists(state_path):
        try: os.remove(state_path)
        except: pass
    if os.path.exists(bat_path):
        try: os.remove(bat_path)
        except: pass

def update_worker(worker_id, task, status):
    with worker_states_lock:
        worker_states[worker_id] = {"task": task, "status": status}

def draw_dashboard(max_workers):
    global first_draw, completed_count, processed_count, failed_tasks, total_tasks, existing_df, years, output_path, server_port
    
    lines = []
    lines.append(f"{colorama.Fore.CYAN}=================== PLAYLIST GENERATOR (PARALEL) ==================={colorama.Style.RESET_ALL}")
    years_str = ", ".join(map(str, years))
    if len(years_str) > 40:
        years_str = years_str[:37] + "..."
        
    display_path = output_path
    if len(display_path) > 40:
        try:
            # Try getting relative path from two directories up
            display_path = os.path.relpath(output_path, os.path.dirname(os.path.dirname(output_path)))
            if len(display_path) > 40:
                display_path = "...\\" + os.path.basename(output_path)
        except:
            display_path = os.path.basename(output_path)
            
    lines.append(f"  Tahun Pencarian      : {colorama.Fore.YELLOW}{years_str}{colorama.Style.RESET_ALL}")
    lines.append(f"  Lokasi File Excel    : {colorama.Fore.GREEN}{display_path}{colorama.Style.RESET_ALL}")
    lines.append(f"  Live Web UI Dashboard: {colorama.Fore.CYAN}http://localhost:{server_port}{colorama.Style.RESET_ALL}")
    lines.append(f"{colorama.Fore.CYAN}--------------------------------------------------------------------{colorama.Style.RESET_ALL}")
    
    # Workers Status
    lines.append(f"{colorama.Fore.YELLOW}STATUS WORKER GENERATOR:{colorama.Style.RESET_ALL}")
    with worker_states_lock:
        for i, w in enumerate(worker_states):
            slot_num = i + 1
            if w['task']:
                task_disp = w['task']
                if len(task_disp) > 30:
                    task_disp = task_disp[:27] + "..."
                status_color = colorama.Fore.GREEN
                if "Web" in w['status']:
                    status_color = colorama.Fore.BLUE
                elif "Target" in w['status']:
                    status_color = colorama.Fore.MAGENTA
                lines.append(f"  Worker {slot_num}: {status_color}{w['status']:18}{colorama.Style.RESET_ALL} | {task_disp}")
            else:
                lines.append(f"  Worker {slot_num}: {colorama.Fore.LIGHTBLACK_EX}Idle{colorama.Style.RESET_ALL}")
                
    lines.append(f"{colorama.Fore.CYAN}--------------------------------------------------------------------{colorama.Style.RESET_ALL}")
    
    # Calculate ETA
    completed_this_run = processed_count - initial_completed_count
    if completed_this_run > 0:
        elapsed = time.time() - run_start_time
        time_per_task = elapsed / completed_this_run
        rem_tasks = total_tasks - processed_count
        eta_seconds = time_per_task * rem_tasks
        eta_str = format_duration(eta_seconds)
    else:
        eta_str = "Menghitung..."
        
    # Progress Bar
    percent = (processed_count / total_tasks) * 100.0 if total_tasks > 0 else 0.0
    completed_blocks = int((percent / 100) * 15)
    remaining_blocks = 15 - completed_blocks
    pbar = "[" + "=" * completed_blocks + "-" * remaining_blocks + "]"
    
    total_songs = len(existing_df) if existing_df is not None else 0
    
    lines.append(f"  Progress Total: {pbar} {percent:.1f}% ({processed_count}/{total_tasks} tugas diproses)")
    lines.append(f"  Estimasi Sisa  : {colorama.Fore.YELLOW}{eta_str}{colorama.Style.RESET_ALL}")
    lines.append(f"  Tugas Sukses   : {colorama.Fore.GREEN}{completed_count}{colorama.Style.RESET_ALL} | Gagal: {colorama.Fore.RED}{len(failed_tasks)}{colorama.Style.RESET_ALL}")
    lines.append(f"  Total Lagu     : {colorama.Fore.GREEN}{total_songs} lagu{colorama.Style.RESET_ALL} (berhasil digabungkan)")
    lines.append(f"{colorama.Fore.CYAN}===================================================================={colorama.Style.RESET_ALL}")
    
    CL = "\033[K"
    output = f"{CL}\n".join(lines) + CL
    
    if not first_draw:
        sys.stdout.write(f"\033[{12 + max_workers}A\r")
        
    sys.stdout.write(output + "\n")
    sys.stdout.flush()
    first_draw = False

def tui_thread_loop(max_workers):
    global running
    while running:
        draw_dashboard(max_workers)
        time.sleep(0.2)

def process_genre_task(year_val, genre_name, task_limit, ydl_opts, worker_id):
    # Stagger thread execution startup slightly to prevent simultaneous query bursts
    time.sleep(random.uniform(0.5, 3.5))

    # 1. Web Scrape
    update_worker(worker_id, f"[{year_val}] {genre_name}", "Web Scraping")
    web_songs = []
    try:
        web_songs = list_generator.scrape_popular_songs_from_web(genre_name, year_val)
    except Exception as e:
        log_error(f"[{year_val}][{genre_name}] Web Scraping Error: {e}")
    
    # 2. Targeted Top Artist Search
    update_worker(worker_id, f"[{year_val}] {genre_name}", "Target Artist YT")
    artist_songs = []
    artists = list_generator.TOP_ARTISTS.get(genre_name, [])[:8]
    
    yt_errors = []
    for art in artists:
        # Sleep interval between queries to look organic
        time.sleep(random.uniform(1.0, 3.0))
        query = f"{art} {year_val}"
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                res = ydl.extract_info(f"ytsearch10:{query}", download=False)
                if res and 'entries' in res:
                    for entry in res['entries']:
                        if not entry:
                            continue
                        title = entry.get('title', '')
                        channel = entry.get('uploader', '')
                        duration = entry.get('duration')
                        if duration and duration > 600:
                            continue
                        p_art, p_title = list_generator.parse_video_title(title, channel)
                        artist_songs.append((p_art, p_title))
        except Exception as e:
            err_msg = str(e)
            yt_errors.append(f"YT Target Search '{query}': {err_msg}")
            log_error(f"[{year_val}][{genre_name}] Error mencari {art}: {err_msg}")
            
    # 3. General YouTube Search (Terpopuler & Viral Hits)
    # Sleep slightly before starting the general search
    time.sleep(random.uniform(1.5, 4.0))
    update_worker(worker_id, f"[{year_val}] {genre_name}", "General YT Search")
    gen_songs = []
    
    general_queries = [
        f"lagu {genre_name} {year_val} terpopuler",
        f"lagu {genre_name} {year_val} viral hits",
        f"lagu {genre_name} {year_val} terbaru",
        f"top {genre_name} songs {year_val}"
    ]
    
    for idx, query in enumerate(general_queries):
        if idx > 0:
            time.sleep(random.uniform(1.5, 3.0))
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                res = ydl.extract_info(f"ytsearch40:{query}", download=False)
                if res and 'entries' in res:
                    for entry in res['entries']:
                        if not entry:
                            continue
                        title = entry.get('title', '')
                        channel = entry.get('uploader', '')
                        duration = entry.get('duration')
                        if duration and duration > 600:
                            continue
                        p_art, p_title = list_generator.parse_video_title(title, channel)
                        gen_songs.append((p_art, p_title))
        except Exception as e:
            err_msg = str(e)
            yt_errors.append(f"YT General Search '{query}': {err_msg}")
            log_error(f"[{year_val}][{genre_name}] General YT Search Error: {err_msg}")
        
    if yt_errors and len(artist_songs) == 0 and len(gen_songs) == 0:
        is_rate_limit = any("429" in err or "Too Many Requests" in err for err in yt_errors)
        if is_rate_limit:
            raise Exception("YouTube rate limit (HTTP 429) terdeteksi. Silakan coba beberapa saat lagi.")
        else:
            raise Exception(f"Pencarian YouTube gagal: {yt_errors[0]}")
        
    genre_results = []
    seen_local = set()
    
    all_candidates = web_songs + artist_songs + gen_songs
    for art, tit in all_candidates:
        if not art or not tit or art == "Penyanyi Tidak Dikenal" or tit == "Judul Tidak Dikenal":
            continue
            
        # Smart online/local validation
        if list_generator.is_suspicious_entry(art, tit):
            corr_art, corr_tit, is_valid = list_generator.validate_song_online(art, tit)
            if not is_valid:
                log_error(f"[{year_val}][{genre_name}] Menyaring keluar lagu tidak valid: {art} - {tit}")
                continue
            art = corr_art
            tit = corr_tit
            
        key = f"{art.lower()} - {tit.lower()}"
        if key not in seen_local:
            seen_local.add(key)
            genre_results.append({
                'Nama Penyanyi': art,
                'Judul Lagu': tit,
                'Kategori': genre_name,
                'Tahun': year_val
            })
            if len(genre_results) >= task_limit:
                break
                
    update_worker(worker_id, "", "Idle")
    return genre_results

def append_to_csv(csv_path, songs_list):
    """Writes a list of songs to a CSV file in a thread-safe, append-only manner."""
    file_exists = os.path.exists(csv_path)
    fieldnames = ['Nama Penyanyi', 'Judul Lagu', 'Kategori', 'Tahun']
    
    with open(csv_path, 'a', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        for song in songs_list:
            writer.writerow(song)

def compile_csv_to_xlsx(csv_path, xlsx_path):
    """Compiles the temporary CSV file into the final sorted Excel sheet and cleans it up."""
    if not os.path.exists(csv_path):
        return
    try:
        df = pd.read_csv(csv_path)
        df.drop_duplicates(subset=['Nama Penyanyi', 'Judul Lagu'], inplace=True)
        df.sort_values(by=['Kategori', 'Tahun', 'Nama Penyanyi', 'Judul Lagu'], inplace=True, ignore_index=True)
        
        # Must end in .xlsx to allow pandas to automatically detect Excel writer engine
        tmp_path = xlsx_path + ".tmp.xlsx"
        df.to_excel(tmp_path, index=False)
        if os.path.exists(tmp_path):
            os.replace(tmp_path, xlsx_path)
            
        try:
            os.remove(csv_path)
        except:
            pass
    except Exception as e:
        log_error(f"Gagal mengompilasi CSV ke Excel: {e}")

def main():
    global completed_count, processed_count, failed_tasks, total_tasks, existing_df, running, first_draw, years, output_path, limit, completed_steps, seen_songs, completed_songs, worker_states
    
    parser = argparse.ArgumentParser(description="YouTube Karaoke Playlist Generator")
    parser.add_argument("--resume", action="store_true", help="Resume previous search session")
    args = parser.parse_args()

    proj_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(proj_dir)
    state_path = os.path.join(proj_dir, "generator_state.json")

    print(f"{colorama.Fore.CYAN}=========================================================={colorama.Style.RESET_ALL}")
    print(f"         YOUTUBE KARAOKE PLAYLIST GENERATOR BOT           ")
    print(f"{colorama.Fore.CYAN}=========================================================={colorama.Style.RESET_ALL}")
    
    is_resumed = False
    
    if args.resume:
        if os.path.exists(state_path):
            try:
                with open(state_path, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                years = state.get("years", [])
                output_path = state.get("output_path", "")
                limit = state.get("limit", 250)
                completed_steps = state.get("completed_steps", [])
                is_resumed = True
                print(f"{colorama.Fore.GREEN} -> Menghubungkan sesi sebelumnya secara otomatis (Resume).{colorama.Style.RESET_ALL}")
            except Exception as e:
                print(f"{colorama.Fore.RED} [Error] Gagal membaca generator_state.json: {e}{colorama.Style.RESET_ALL}")
                sys.exit(1)
        else:
            print(f"{colorama.Fore.RED} [Error] File generator_state.json tidak ditemukan. Sesi tidak bisa dilanjutkan.{colorama.Style.RESET_ALL}")
            sys.exit(1)
            
    elif os.path.exists(state_path):
        print(f"\n{colorama.Fore.YELLOW} [INFO] Terdeteksi sesi sebelumnya yang belum selesai.{colorama.Style.RESET_ALL}")
        choice_resume = input(" Apakah Anda ingin melanjutkan sesi sebelumnya? (y/n, default y): ").strip().lower()
        if choice_resume != 'n':
            try:
                with open(state_path, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                years = state.get("years", [])
                output_path = state.get("output_path", "")
                limit = state.get("limit", 250)
                completed_steps = state.get("completed_steps", [])
                is_resumed = True
                write_resume_bat(proj_dir)
                print(f"{colorama.Fore.GREEN} -> Melanjutkan sesi sebelumnya.{colorama.Style.RESET_ALL}")
            except Exception as e:
                print(f"{colorama.Fore.RED} (Gagal memulihkan sesi sebelumnya: {e}. Mulai sesi baru...){colorama.Style.RESET_ALL}")

    if not is_resumed:
        print(f" Bot ini akan mendeteksi lagu populer di YouTube secara massal.\n")

        while True:
            input_str = input(f" Masukkan tahun (Contoh: '2024', '2020-2026', '2020, 2022'): ").strip()
            try:
                years = parse_years_input(input_str)
                break
            except ValueError as e:
                print(f"{colorama.Fore.RED} [Error] {str(e)}{colorama.Style.RESET_ALL}")

        years_disp = ", ".join(map(str, years))
        print(f" -> Tahun yang akan dicari: {colorama.Fore.GREEN}{years_disp}{colorama.Style.RESET_ALL} (total {len(years)} tahun)")

        if len(years) == 1:
            years_suffix = f"{years[0]}"
        else:
            years_suffix = f"{min(years)}-{max(years)}"
        default_excel_path = os.path.join(proj_dir, f"list lagu new {years_suffix}.xlsx")
        print(f"\n Lokasi file Excel output default: {colorama.Fore.YELLOW}{default_excel_path}{colorama.Style.RESET_ALL}")
        custom_path = input(" Tekan Enter untuk default, atau masukkan path lengkap file Excel baru: ").strip()
        
        if custom_path:
            output_path = custom_path.replace('"', '').replace("'", "")
        else:
            output_path = default_excel_path

        print(f"\n {colorama.Fore.CYAN}Berapa banyak lagu yang ingin diambil per genre per tahun?{colorama.Style.RESET_ALL}")
        print(" [1] 100 lagu (Total ~1.200 lagu per tahun)")
        print(" [2] 250 lagu (Total ~3.000 lagu per tahun)")
        print(" [3] 500 lagu (Total ~6.000 lagu per tahun)")
        choice_limit = input(" Pilih opsi (1/2/3) atau ketik jumlah custom sendiri (100 - 500): ").strip()
        
        if choice_limit == "1":
            limit = 100
        elif choice_limit == "3":
            limit = 500
        elif choice_limit.isdigit():
            limit = int(choice_limit)
            if limit < 10:
                limit = 10
        else:
            limit = 250

        write_resume_bat(proj_dir)
        save_generator_state(state_path, {
            "years": years,
            "output_path": output_path,
            "limit": limit,
            "completed_steps": []
        })

    output_dir = os.path.dirname(output_path) or os.getcwd()
    os.makedirs(output_dir, exist_ok=True)

    # 4. Anti-Collision and Smart Read (Database & History checks)
    # Load completed history to skip already downloaded songs (from root folder)
    history_path = os.path.join(parent_dir, "download_history.json")
    if os.path.exists(history_path):
        try:
            with open(history_path, 'r', encoding='utf-8') as f:
                history = json.load(f)
                for key, info in history.items():
                    if info.get('status') == 'Completed':
                        completed_songs.add(key.lower().strip())
            print(f" -> Berhasil membaca {len(completed_songs)} lagu yang SUDAH SELESAI dari riwayat download.")
        except Exception as e:
            print(f" (Peringatan: Gagal membaca riwayat download: {e})")

    # Load existing target Excel file (if any)
    if os.path.exists(output_path):
        try:
            temp_df = pd.read_excel(output_path)
            if not temp_df.empty and 'Nama Penyanyi' in temp_df.columns:
                existing_df = temp_df
                for idx, row in existing_df.iterrows():
                    art = str(row.get('Nama Penyanyi', '')).strip().lower()
                    tit = str(row.get('Judul Lagu', '')).strip().lower()
                    if art and tit:
                        seen_songs.add(f"{art} - {tit}")
                print(f" -> Berhasil membaca {len(existing_df)} lagu dari file Excel lama.")
        except Exception as e:
            print(f" (Peringatan: Gagal membaca file Excel lama: {e})")

    # Load existing temporary CSV file (if any, from interrupted session)
    csv_path = output_path.replace('.xlsx', '.csv')
    if os.path.exists(csv_path):
        try:
            temp_csv_df = pd.read_csv(csv_path)
            if not temp_csv_df.empty and 'Nama Penyanyi' in temp_csv_df.columns:
                for idx, row in temp_csv_df.iterrows():
                    art = str(row.get('Nama Penyanyi', '')).strip().lower()
                    tit = str(row.get('Judul Lagu', '')).strip().lower()
                    if art and tit:
                        seen_songs.add(f"{art} - {tit}")
                print(f" -> Berhasil membaca {len(temp_csv_df)} lagu dari file CSV sementara.")
                
                # Combine CSV data into existing_df for TUI display
                if existing_df is not None:
                    existing_df = pd.concat([existing_df, temp_csv_df], ignore_index=True)
                    existing_df.drop_duplicates(subset=['Nama Penyanyi', 'Judul Lagu'], inplace=True)
                else:
                    existing_df = temp_csv_df
        except Exception as e:
            print(f" (Peringatan: Gagal membaca file CSV sementara: {e})")

    # Start Web UI server in background
    start_web_ui_server(port=8000)

    # Initialize workers (6 threads max for parallel scraping)
    max_workers = 6
    worker_states = [{"task": "", "status": "Idle"} for _ in range(max_workers)]
    
    # 5. Build task queue
    tasks_to_run = []
    completed_count = 0
    processed_count = 0
    failed_tasks = []
    
    for year_val in years:
        for genre_name in list_generator.TOP_ARTISTS.keys():
            step_key = f"{year_val} - {genre_name}"
            if step_key in completed_steps:
                completed_count += 1
                processed_count += 1
            else:
                tasks_to_run.append((year_val, genre_name, step_key))
                
    total_tasks = len(years) * len(list_generator.TOP_ARTISTS)
    
    global run_start_time, initial_completed_count
    run_start_time = time.time()
    initial_completed_count = completed_count
    
    if len(completed_steps) >= total_tasks:
        cleanup_state_files(proj_dir, state_path)
        # Final XLSX compilation
        compile_csv_to_xlsx(csv_path, output_path)
        print(f"\n{colorama.Fore.GREEN} Semua tugas tahun/genre dalam list sudah selesai diproses!{colorama.Style.RESET_ALL}")
        return

    # Clear screen for TUI drawing
    os.system('cls' if os.name == 'nt' else 'clear')
    
    ydl_opts = {
        'extract_flat': True,
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'logger': list_generator.SearchLogger(),
        'sleep_interval': 1,
        'max_sleep_interval': 3,
    }
    
    # Start TUI dashboard thread
    running = True
    tui_thread = threading.Thread(target=tui_thread_loop, args=(max_workers,))
    tui_thread.daemon = True
    tui_thread.start()
    
    # Run multithreaded executor
    try:
        active_thread_ids = {}
        active_thread_ids_lock = threading.Lock()
        
        def get_worker_slot():
            ident = threading.get_ident()
            with active_thread_ids_lock:
                if ident not in active_thread_ids:
                    used = set(active_thread_ids.values())
                    for i in range(max_workers):
                        if i not in used:
                            active_thread_ids[ident] = i
                            break
                return active_thread_ids.get(ident, 0)
                
        def release_worker_slot():
            ident = threading.get_ident()
            with active_thread_ids_lock:
                active_thread_ids.pop(ident, None)

        def thread_worker_wrapper(year_val, genre_name):
            slot = get_worker_slot()
            try:
                res = process_genre_task(year_val, genre_name, limit, ydl_opts, slot)
                return res
            finally:
                release_worker_slot()

        from concurrent.futures import wait, FIRST_COMPLETED
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_task = {}
            task_retry_counts = {}
            active_futures = set()
            
            # Helper to fill available worker slots
            def queue_next_tasks():
                while len(active_futures) < max_workers and tasks_to_run:
                    y_val, g_name, s_key = tasks_to_run.pop(0)
                    fut = executor.submit(thread_worker_wrapper, y_val, g_name)
                    future_to_task[fut] = (y_val, g_name, s_key)
                    active_futures.add(fut)
                    
            # Submit initial batch
            queue_next_tasks()
            
            while active_futures:
                # Wait for any task to complete
                done, not_done = wait(active_futures, return_when=FIRST_COMPLETED)
                
                for future in done:
                    active_futures.remove(future)
                    year_val, genre_name, step_key = future_to_task.pop(future)
                    
                    try:
                        genre_songs = future.result()
                        
                        with excel_write_lock:
                            if genre_songs:
                                new_valid_songs = []
                                for song in genre_songs:
                                    song_key = f"{song['Nama Penyanyi'].lower()} - {song['Judul Lagu'].lower()}"
                                    if song_key not in seen_songs and song_key not in completed_songs:
                                        seen_songs.add(song_key)
                                        new_valid_songs.append(song)
                                        
                                if new_valid_songs:
                                    # Append directly to CSV
                                    append_to_csv(csv_path, new_valid_songs)
                                    
                                    # Load into memory to update TUI total count
                                    df_new = pd.DataFrame(new_valid_songs)
                                    if existing_df is not None:
                                        existing_df = pd.concat([existing_df, df_new], ignore_index=True)
                                    else:
                                        existing_df = df_new
                                            
                        completed_steps.append(step_key)
                        completed_count += 1
                        processed_count += 1
                        
                        state_data = {
                            "years": years,
                            "output_path": output_path,
                            "limit": limit,
                            "completed_steps": completed_steps
                        }
                        save_generator_state(state_path, state_data)
                    except Exception as task_err:
                        err_msg = str(task_err)
                        log_error(f"Tugas {step_key} gagal: {err_msg}")
                        
                        # Auto-retry logic: Put back to the end of the queue up to 3 times
                        retries = task_retry_counts.get(step_key, 0)
                        if retries < 3:
                            task_retry_counts[step_key] = retries + 1
                            log_error(f"Mengantrekan kembali {step_key} ke antrean belakang (Coba ke-{retries + 2})")
                            # Add to the end of the queue
                            tasks_to_run.append((year_val, genre_name, step_key))
                        else:
                            # Permanently failed for this session
                            failed_tasks.append((step_key, err_msg))
                            processed_count += 1
                            
                # Fill up worker slots again
                queue_next_tasks()

    except KeyboardInterrupt:
        pass
    finally:
        running = False
        tui_thread.join(timeout=1.0)
        
        # Compile temporary CSV into final sorted Excel sheet
        if os.path.exists(csv_path):
            compile_csv_to_xlsx(csv_path, output_path)
            
        # Clean up files if fully completed
        if len(completed_steps) >= total_tasks:
            cleanup_state_files(proj_dir, state_path)
            first_draw = True
            os.system('cls' if os.name == 'nt' else 'clear')
            draw_dashboard(max_workers)
            print(f"\n====================================================================")
            print(f"             SCRAPING LIST LAGU SELESAI 100%                        ")
            print(f"====================================================================")
            total_songs = len(existing_df) if existing_df is not None else 0
            print(f" Total Lagu Berhasil Dikompilasi: {total_songs} lagu")
            print(f" Hasil disimpan di             : {output_path}")
            print(f"====================================================================")
            print(" Silakan jalankan Downloader (run.bat) untuk mendownload playlist ini.\n")
        else:
            first_draw = True
            os.system('cls' if os.name == 'nt' else 'clear')
            draw_dashboard(max_workers)
            print(f"\n{colorama.Fore.YELLOW}[WARN] Sesi scraping selesai dengan kegagalan / dihentikan.{colorama.Style.RESET_ALL}")
            if failed_tasks:
                print(f" {colorama.Fore.RED}Terjadi {len(failed_tasks)} kegagalan selama proses pencarian (e.g. rate limit/network).{colorama.Style.RESET_ALL}")
                print(f" Rincian error telah disimpan di: {colorama.Fore.CYAN}generator_error.log{colorama.Style.RESET_ALL}")
            print(f"Untuk mengulangi tugas yang gagal/belum selesai, silakan jalankan kembali: {colorama.Fore.GREEN}resume_generator.bat{colorama.Style.RESET_ALL}\n")

if __name__ == "__main__":
    main()
