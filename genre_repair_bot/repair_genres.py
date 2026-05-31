import os
import sys
import re
import csv
import json
import time
import shutil
import random
import threading
import queue
import urllib.request
import urllib.parse
import http.server
import socketserver
from collections import Counter
import pandas as pd
import colorama

colorama.init()

# ============================================================
# CONFIGURATION
# ============================================================
NUM_WORKERS = 50
WEB_UI_PORT = 8003

# Strict list of valid standardized genres
VALID_GENRES = {
    "Dangdut", "Pop Indo", "Pop Barat", "Pop Melayu",
    "Rock Indo", "Rock Barat", "Rock Melayu",
    "K-Pop", "J-Pop", "Mandopop",
    "Jazz", "Reggae", "Hip Hop", "R&B", "Electronic",
    "Religi", "Anak-Anak", "Soundtrack", "Lagu Daerah"
}

INDONESIAN_WORDS = {
    'yang', 'dan', 'dengan', 'untuk', 'pada', 'ke', 'dari', 'dalam', 'ini', 'itu',
    'aku', 'kamu', 'dia', 'mereka', 'kita', 'kami', 'kau', 'mu', 'ku', 'nya',
    'cinta', 'hati', 'rasa', 'bisa', 'tidak', 'tak', 'jangan', 'akan', 'sudah',
    'selamat', 'pagi', 'siang', 'malam', 'hari', 'jalan', 'satu', 'dua', 'tiga',
    'kasih', 'sayang', 'rindu', 'kembali', 'pergi', 'datang', 'lihat', 'dengar',
    'suka', 'ingin', 'tahu', 'mau', 'ada', 'tiada', 'lagu', 'nyanyi', 'gitar',
    'kunci', 'lirik', 'sakit', 'senang', 'sedih', 'bahagia', 'selamanya', 'sampai',
    'mati', 'hidup', 'jiwa', 'raga', 'bintang', 'bulan', 'matahari', 'langit',
    'ojo', 'dibandingke', 'tresno', 'loro', 'ati', 'aku', 'kowe', 'siji', 'loro', 'telu'
}

MALAYSIAN_ARTISTS = {
    'exists', 'slam', 'ukays', 'siti nurhaliza', 'amy search', 'search', 'wings',
    'iklim', 'p. ramlee', 'yuna', 'saleem', 'tajul', 'spoon', 'spin', 'screen',
    'lestari', 'eye', 'stings', 'mega', 'flophouse', 'insomniacks', 'masdo'
}

# ============================================================
# SHARED STATE FOR WEB UI
# ============================================================
ui_state = {
    "total": 0,
    "processed": 0,
    "start_time": 0,
    "genre_counts": Counter(),
    "recent": [],       # list of last 100 items: {artist, title, genre, source, time}
    "workers": {},      # worker_id -> {artist, status, count}
    "running": True,
    "unique_artists_cached": 0,
    "unique_artists_searched": 0,
}
ui_lock = threading.Lock()

# Locks for thread-safety
csv_write_lock = threading.Lock()
json_write_lock = threading.Lock()
console_lock = threading.Lock()

# ============================================================
# UTILITY FUNCTIONS
# ============================================================
def is_indonesian_text(text):
    if not text:
        return False
    words = re.sub(r'[^a-z\s]', '', text.lower()).split()
    matched = sum(1 for w in words if w in INDONESIAN_WORDS)
    return matched >= 1

def safe_request(url, timeout=6):
    headers = {
        'User-Agent': 'DimpiKaraokeGenreRepairBot/2.0 (contact: dimpi@example.com; search profiling tool)'
    }
    req = urllib.request.Request(url, headers=headers)
    max_retries = 3
    base_sleep = 2
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode('utf-8', errors='ignore')
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(base_sleep)
                base_sleep *= 2
                continue
            return None
        except Exception:
            time.sleep(1)
            continue
    return None

def query_wiki_list(query, lang='id'):
    encoded = urllib.parse.quote(query)
    url = f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search&srsearch={encoded}&format=json"
    html_content = safe_request(url)
    if html_content:
        try:
            data = json.loads(html_content)
            search_results = data.get('query', {}).get('search', [])
            return [{'title': item.get('title', ''), 'snippet': item.get('snippet', '')} for item in search_results[:3]]
        except Exception:
            pass
    return []

def query_itunes_genre(artist):
    url = f"https://itunes.apple.com/search?term={urllib.parse.quote(artist)}&limit=3&entity=musicTrack"
    html_content = safe_request(url)
    if html_content:
        try:
            data = json.loads(html_content)
            results = data.get('results', [])
            return [r.get('primaryGenreName', '') for r in results]
        except Exception:
            pass
    return []

# ============================================================
# CLASSIFICATION ENGINE
# ============================================================
def classify_origin_from_text(text):
    text_lower = text.lower()
    if any(x in text_lower for x in ['malaysia', 'kuala lumpur', 'johor', 'selangor', 'sarawak', 'sabah']):
        return "Malaysia"
    if any(x in text_lower for x in ['korea', 'seoul', 'k-pop', 'kpop']):
        return "Korea"
    if any(x in text_lower for x in ['jepang', 'tokyo', 'osaka', 'j-pop', 'jpop', 'anime', 'nihon']):
        return "Jepang"
    if any(x in text_lower for x in ['tiongkok', 'china', 'cina', 'taiwan', 'hong kong', 'hongkong', 'mandarin', 'c-pop']):
        return "Mandarin"
    if any(x in text_lower for x in ['amerika', 'inggris', 'serikat', 'london', 'new york', 'kanada', 'australia', 'jerman', 'prancis', 'italian', 'spanyol', 'swedia', 'united states', 'united kingdom']):
        return "Barat"
    indo_indicators = [
        'grup musik', 'grup band', 'penyanyi', 'musisi', 'dangdut', 'pedangdut',
        'vokalis', 'lagu', 'album', 'boyolali', 'bandung', 'jakarta', 'yogyakarta',
        'surabaya', 'semarang', 'medan', 'solo', 'koplo', 'campursari', 'pop',
        'indonesia', 'indonesian', 'jogjakarta', 'jogja', 'denpasar', 'bali',
        'sunda', 'jawa', 'sumatera', 'sulawesi', 'kalimantan', 'maluku', 'papua'
    ]
    if any(x in text_lower for x in indo_indicators):
        return "Indonesia"
    return None

def classify_artist_origin(artist, wiki_id_list, wiki_en_list, itunes_genres):
    artist_lower = artist.lower().strip()
    if any(m_art in artist_lower for m_art in MALAYSIAN_ARTISTS):
        return "Malaysia"
    if wiki_id_list:
        first_origin = classify_origin_from_text(wiki_id_list[0]['snippet'] + " " + wiki_id_list[0]['title'])
        if first_origin:
            return first_origin
    if wiki_en_list:
        first_origin = classify_origin_from_text(wiki_en_list[0]['snippet'] + " " + wiki_en_list[0]['title'])
        if first_origin:
            return first_origin
    if wiki_id_list:
        combined_id = " ".join([x['snippet'] + " " + x['title'] for x in wiki_id_list])
        combined_origin = classify_origin_from_text(combined_id)
        if combined_origin:
            return combined_origin
    if wiki_en_list:
        combined_en = " ".join([x['snippet'] + " " + x['title'] for x in wiki_en_list])
        combined_origin = classify_origin_from_text(combined_en)
        if combined_origin:
            return combined_origin
    if itunes_genres:
        joined_genres = " ".join(itunes_genres).lower()
        if any(x in joined_genres for x in ['dangdut', 'indo', 'indonesian']):
            return "Indonesia"
        if any(x in joined_genres for x in ['k-pop', 'kpop', 'korean']):
            return "Korea"
        if any(x in joined_genres for x in ['j-pop', 'jpop', 'japanese', 'anime']):
            return "Jepang"
        if any(x in joined_genres for x in ['c-pop', 'cpop', 'mandopop', 'chinese', 'taiwanese', 'mandarin']):
            return "Mandarin"
        if any(x in joined_genres for x in ['malay', 'malaysian']):
            return "Malaysia"
        if any(x in joined_genres for x in ['pop', 'rock', 'metal', 'alternative', 'country', 'jazz', 'blues', 'punk', 'hip hop', 'r&b']):
            if is_indonesian_text(artist):
                return "Indonesia"
            else:
                return "Barat"
    if is_indonesian_text(artist):
        return "Indonesia"
    english_words = {'the', 'you', 'me', 'love', 'i', 'and', 'to', 'a', 'in', 'it', 'is', 'of', 'for', 'on', 'my', 'your', 'with', 'that', 'this'}
    words = re.sub(r'[^a-z\s]', '', artist.lower()).split()
    if sum(1 for w in words if w in english_words) >= 1:
        return "Barat"
    return "Indonesia"

def detect_style_from_text(text):
    text = text.lower()
    def has_word(pattern, txt):
        return bool(re.search(r'\b(' + pattern + r')\b', txt))
    if has_word('dangdut|koplo|campursari|tarling|pedangdut', text):
        return 'dangdut'
    if has_word('christian|gospel|inspirational|spiritual|religi|nasyid|qasidah|sholawat|rohani|islamic|sholawat|nasid', text):
        return 'religi'
    if has_word('children|kids|cilik|anak-anak', text) or 'lagu anak' in text or 'penyanyi cilik' in text:
        return 'anak-anak'
    if has_word('reggae|ska|rocksteady|dub', text):
        return 'reggae'
    if has_word('hip-hop|hip hop|hiphop|rap|rapper', text):
        return 'hip hop'
    if has_word('jazz|swing|bebop', text):
        return 'jazz'
    if 'r&b' in text or has_word('soul|funk|motown', text):
        return 'r&b'
    if has_word('dance|electronic|edm|house|techno|trance|synthpop|dubstep|electro', text):
        return 'electronic'
    if has_word('rock|metal|alternative|punk|grunge|hardcore|hard-rock|indie-rock', text):
        return 'rock'
    if has_word('soundtrack|ost|score', text) or 'anime theme' in text or 'theme song' in text:
        return 'soundtrack'
    if has_word('tradisional|traditional|folk|gamelan|karawitan|keroncong|angklung|sinden', text) or 'lagu daerah' in text or 'musik tradisional' in text:
        return 'traditional'
    return 'pop'

def combine_origin_and_style(origin, style, wiki_context=""):
    if origin == "Korea":
        return "K-Pop"
    if origin == "Jepang":
        return "J-Pop"
    if origin == "Mandarin":
        return "Mandopop"
    if style == "religi":
        return "Religi"
    if style == "anak-anak":
        return "Anak-Anak"
    if style == "soundtrack":
        return "Soundtrack"
    if style == "dangdut":
        return "Dangdut"
    if style == "jazz":
        return "Jazz"
    if style == "reggae":
        return "Reggae"
    if style == "hip hop":
        return "Hip Hop"
    if style == "r&b":
        return "R&B"
    if style == "electronic":
        return "Electronic"
    if origin == "Malaysia":
        if style == "rock":
            return "Rock Melayu"
        return "Pop Melayu"
    if origin == "Indonesia":
        if style == "traditional":
            traditional_indicators = ['daerah', 'tradisional', 'sunda', 'jawa', 'batak', 'minang', 'folklore', 'gamelan', 'karawitan', 'angklung', 'tarling']
            if any(ind in wiki_context.lower() for ind in traditional_indicators):
                return "Lagu Daerah"
            return "Pop Indo"
        if style == "rock":
            return "Rock Indo"
        return "Pop Indo"
    if style == "rock":
        return "Rock Barat"
    return "Pop Barat"

def get_standardized_genre(artist):
    wiki_id_list = query_wiki_list(artist, "id")
    if wiki_id_list and wiki_id_list[0]['title'].lower() != artist.lower():
        redirect_wiki = query_wiki_list(wiki_id_list[0]['title'], "id")
        if redirect_wiki:
            wiki_id_list = redirect_wiki
    wiki_en_list = query_wiki_list(artist, "en")
    if wiki_en_list and wiki_en_list[0]['title'].lower() != artist.lower():
        redirect_wiki = query_wiki_list(wiki_en_list[0]['title'], "en")
        if redirect_wiki:
            wiki_en_list = redirect_wiki
    itunes_genres = query_itunes_genre(artist)
    origin = classify_artist_origin(artist, wiki_id_list, wiki_en_list, itunes_genres)
    wiki_context = ""
    if wiki_id_list:
        wiki_context += " ".join([x['snippet'] + " " + x['title'] for x in wiki_id_list])
    if wiki_en_list:
        wiki_context += " " + " ".join([x['snippet'] + " " + x['title'] for x in wiki_en_list])
    primary_itunes_genre = itunes_genres[0].lower() if itunes_genres else ""
    wiki_style = detect_style_from_text(wiki_context)
    itunes_style = detect_style_from_text(primary_itunes_genre)
    if wiki_style != 'pop':
        style = wiki_style
    elif itunes_style != 'pop':
        style = itunes_style
    else:
        all_itunes_text = " ".join(itunes_genres).lower()
        combined_style = detect_style_from_text(all_itunes_text)
        if combined_style != 'pop':
            style = combined_style
        else:
            style = 'pop'
    genre = combine_origin_and_style(origin, style, wiki_context)
    return genre

# ============================================================
# WEB UI SERVER
# ============================================================
def get_web_ui_html():
    return r'''<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Genre Repair Bot — Live Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{--bg:#0b0e14;--card:#13171f;--card2:#1a1f2b;--border:#1e2533;--accent:#6c5ce7;--accent2:#a29bfe;--green:#00b894;--yellow:#fdcb6e;--red:#e17055;--cyan:#00cec9;--text:#e0e6f0;--text2:#8892a4;--text3:#5a6378}
body{font-family:'Inter',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;overflow-x:hidden}
.container{max-width:1400px;margin:0 auto;padding:20px}
header{text-align:center;padding:30px 0 20px;position:relative}
header::before{content:'';position:absolute;top:0;left:50%;transform:translateX(-50%);width:200px;height:3px;background:linear-gradient(90deg,transparent,var(--accent),transparent);border-radius:2px}
h1{font-size:28px;font-weight:800;background:linear-gradient(135deg,var(--accent2),var(--cyan));-webkit-background-clip:text;-webkit-text-fill-color:transparent;letter-spacing:-0.5px}
.subtitle{color:var(--text2);font-size:13px;margin-top:4px;font-weight:400}
.grid{display:grid;gap:16px;margin-top:20px}
.top-row{grid-template-columns:1fr 1fr 1fr 1fr;gap:16px}
.mid-row{grid-template-columns:1fr 1fr;gap:16px}
.bot-row{grid-template-columns:1fr;gap:16px}
.card{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:20px;position:relative;overflow:hidden;transition:border-color 0.3s}
.card:hover{border-color:var(--accent)}
.card-label{font-size:11px;text-transform:uppercase;letter-spacing:1.5px;color:var(--text3);font-weight:600;margin-bottom:8px}
.card-value{font-size:36px;font-weight:800;letter-spacing:-1px}
.card-sub{font-size:12px;color:var(--text2);margin-top:4px}
.accent-val{color:var(--accent2)}
.green-val{color:var(--green)}
.yellow-val{color:var(--yellow)}
.cyan-val{color:var(--cyan)}

/* Progress bar */
.progress-outer{width:100%;height:28px;background:var(--card2);border-radius:14px;overflow:hidden;position:relative;margin-top:12px}
.progress-inner{height:100%;background:linear-gradient(90deg,var(--accent),var(--cyan));border-radius:14px;transition:width 0.6s ease;position:relative;min-width:2px}
.progress-inner::after{content:'';position:absolute;top:0;left:0;right:0;bottom:0;background:linear-gradient(90deg,transparent 0%,rgba(255,255,255,0.08) 50%,transparent 100%);animation:shimmer 2s infinite}
@keyframes shimmer{0%{transform:translateX(-100%)}100%{transform:translateX(100%)}}
.progress-label{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);font-size:12px;font-weight:700;color:white;text-shadow:0 1px 3px rgba(0,0,0,0.5);z-index:2}

/* Workers */
.workers-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:6px;margin-top:10px}
.worker-pill{background:var(--card2);border:1px solid var(--border);border-radius:10px;padding:10px 12px;font-size:11px;transition:all 0.3s}
.worker-pill.active{border-color:var(--green);background:rgba(0,184,148,0.06)}
.worker-pill .wid{font-weight:700;color:var(--accent2);font-size:10px;text-transform:uppercase;letter-spacing:1px}
.worker-pill .wartist{color:var(--text);font-weight:500;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:180px}
.worker-pill .wcount{color:var(--text3);font-size:10px;margin-top:2px}

/* Genre chart */
.genre-bars{margin-top:10px;max-height:360px;overflow-y:auto}
.genre-bars::-webkit-scrollbar{width:4px}
.genre-bars::-webkit-scrollbar-thumb{background:var(--border);border-radius:4px}
.gbar{display:flex;align-items:center;margin-bottom:6px;gap:10px}
.gbar-label{font-size:12px;font-weight:500;min-width:100px;text-align:right;color:var(--text2)}
.gbar-track{flex:1;height:22px;background:var(--card2);border-radius:6px;overflow:hidden;position:relative}
.gbar-fill{height:100%;border-radius:6px;transition:width 0.5s ease;min-width:2px}
.gbar-count{font-size:11px;font-weight:600;color:var(--text3);min-width:50px;text-align:left}

/* Table */
.table-wrap{max-height:400px;overflow-y:auto;margin-top:10px;border-radius:10px;border:1px solid var(--border)}
.table-wrap::-webkit-scrollbar{width:4px}
.table-wrap::-webkit-scrollbar-thumb{background:var(--border);border-radius:4px}
table{width:100%;border-collapse:collapse;font-size:12px}
thead{position:sticky;top:0;z-index:1}
th{background:var(--card2);color:var(--text3);font-weight:600;text-transform:uppercase;letter-spacing:1px;font-size:10px;padding:10px 12px;text-align:left;border-bottom:1px solid var(--border)}
td{padding:8px 12px;border-bottom:1px solid var(--border);color:var(--text2)}
tr:hover td{background:rgba(108,92,231,0.04);color:var(--text)}
.badge{display:inline-block;padding:2px 8px;border-radius:6px;font-size:10px;font-weight:600;background:rgba(108,92,231,0.15);color:var(--accent2)}
.badge-web{background:rgba(0,206,201,0.12);color:var(--cyan)}
.badge-cache{background:rgba(253,203,110,0.12);color:var(--yellow)}

.status-dot{display:inline-block;width:6px;height:6px;border-radius:50%;margin-right:6px;animation:pulse 1.5s infinite}
.status-dot.live{background:var(--green)}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.4}}

@media(max-width:900px){.top-row{grid-template-columns:1fr 1fr}.mid-row{grid-template-columns:1fr}.workers-grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:600px){.top-row{grid-template-columns:1fr}.workers-grid{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="container">
<header>
<h1>🎵 Genre Repair Bot</h1>
<p class="subtitle"><span class="status-dot live"></span>Live Dashboard — 30 Workers Parallel</p>
</header>

<div class="grid top-row">
  <div class="card"><div class="card-label">Terproses</div><div class="card-value accent-val" id="processed">0</div><div class="card-sub" id="total-sub">dari 0 lagu</div></div>
  <div class="card"><div class="card-label">Persentase</div><div class="card-value green-val" id="pct">0.0%</div><div class="card-sub" id="speed-sub">— lagu/menit</div></div>
  <div class="card"><div class="card-label">Sisa Waktu (est.)</div><div class="card-value yellow-val" id="eta">—</div><div class="card-sub" id="elapsed-sub">elapsed: 0m</div></div>
  <div class="card"><div class="card-label">Artis Unik</div><div class="card-value cyan-val" id="artists">0</div><div class="card-sub" id="artists-sub">cached: 0 | searched: 0</div></div>
</div>

<div class="card" style="margin-top:16px">
  <div class="card-label">Progress Keseluruhan</div>
  <div class="progress-outer"><div class="progress-inner" id="prog-bar" style="width:0%"></div><div class="progress-label" id="prog-label">0 / 0</div></div>
</div>

<div class="grid mid-row" style="margin-top:16px">
  <div class="card">
    <div class="card-label">Worker Status</div>
    <div class="workers-grid" id="workers"></div>
  </div>
  <div class="card">
    <div class="card-label">Distribusi Genre</div>
    <div class="genre-bars" id="genre-bars"></div>
  </div>
</div>

<div class="grid bot-row" style="margin-top:16px">
  <div class="card">
    <div class="card-label">100 Klasifikasi Terakhir</div>
    <div class="table-wrap">
      <table><thead><tr><th>#</th><th>Penyanyi</th><th>Judul</th><th>Genre</th><th>Sumber</th></tr></thead><tbody id="recent-body"></tbody></table>
    </div>
  </div>
</div>
</div>

<script>
const GENRE_COLORS = {
  "Pop Indo":"#6c5ce7","Pop Barat":"#a29bfe","Pop Melayu":"#fd79a8",
  "Rock Indo":"#e17055","Rock Barat":"#d63031","Rock Melayu":"#e84393",
  "Dangdut":"#00b894","K-Pop":"#0984e3","J-Pop":"#00cec9","Mandopop":"#fdcb6e",
  "Jazz":"#636e72","Reggae":"#55efc4","Hip Hop":"#fab1a0","R&B":"#dfe6e9",
  "Electronic":"#74b9ff","Religi":"#ffeaa7","Anak-Anak":"#ff7675",
  "Soundtrack":"#b2bec3","Lagu Daerah":"#81ecec"
};

async function refresh(){
  try{
    const r=await fetch('/api/status');
    const d=await r.json();
    document.getElementById('processed').textContent=d.processed.toLocaleString();
    document.getElementById('total-sub').textContent='dari '+d.total.toLocaleString()+' lagu';
    const pct=d.total>0?(d.processed/d.total*100):0;
    document.getElementById('pct').textContent=pct.toFixed(1)+'%';
    document.getElementById('prog-bar').style.width=pct+'%';
    document.getElementById('prog-label').textContent=d.processed.toLocaleString()+' / '+d.total.toLocaleString();

    const elapsed=d.elapsed||0;
    const em=Math.floor(elapsed/60);
    const es=Math.floor(elapsed%60);
    document.getElementById('elapsed-sub').textContent='elapsed: '+em+'m '+es+'s';
    const speed=elapsed>0?(d.processed/elapsed*60):0;
    document.getElementById('speed-sub').textContent=speed.toFixed(1)+' lagu/menit';

    if(speed>0 && d.processed<d.total){
      const remaining=(d.total-d.processed)/speed;
      const rh=Math.floor(remaining/60);
      const rm=Math.floor(remaining%60);
      document.getElementById('eta').textContent=rh>0?(rh+'j '+rm+'m'):(rm+'m');
    } else if(d.processed>=d.total && d.total>0){
      document.getElementById('eta').textContent='Selesai!';
    }

    document.getElementById('artists').textContent=(d.cached+d.searched).toLocaleString();
    document.getElementById('artists-sub').textContent='cached: '+d.cached+' | searched: '+d.searched;

    // Workers
    let whtml='';
    for(let i=1;i<=30;i++){
      const w=d.workers[String(i)]||{artist:'—',status:'idle',count:0};
      const cls=w.status==='active'?'active':'';
      whtml+='<div class="worker-pill '+cls+'"><div class="wid">Worker #'+i+'</div><div class="wartist">'+escHtml(w.artist)+'</div><div class="wcount">'+w.count+' proses</div></div>';
    }
    document.getElementById('workers').innerHTML=whtml;

    // Genre bars
    const genres=d.genre_counts||{};
    const sorted=Object.entries(genres).sort((a,b)=>b[1]-a[1]);
    const maxV=sorted.length>0?sorted[0][1]:1;
    let ghtml='';
    for(const [g,c] of sorted){
      const w=Math.max(2,c/maxV*100);
      const col=GENRE_COLORS[g]||'#6c5ce7';
      ghtml+='<div class="gbar"><div class="gbar-label">'+escHtml(g)+'</div><div class="gbar-track"><div class="gbar-fill" style="width:'+w+'%;background:'+col+'"></div></div><div class="gbar-count">'+c.toLocaleString()+'</div></div>';
    }
    document.getElementById('genre-bars').innerHTML=ghtml;

    // Recent
    const recent=d.recent||[];
    let rhtml='';
    for(let i=0;i<recent.length;i++){
      const r=recent[i];
      const badge=r.source==='Web Search'?'badge-web':'badge-cache';
      rhtml+='<tr><td>'+(i+1)+'</td><td>'+escHtml(r.artist)+'</td><td>'+escHtml(r.title)+'</td><td><span class="badge">'+escHtml(r.genre)+'</span></td><td><span class="badge '+badge+'">'+escHtml(r.source)+'</span></td></tr>';
    }
    document.getElementById('recent-body').innerHTML=rhtml;
  }catch(e){}
}

function escHtml(t){if(!t)return'';return t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
setInterval(refresh,1500);
refresh();
</script>
</body>
</html>'''

class DashboardHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Silence HTTP logs

    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            html = get_web_ui_html()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))
        elif self.path == '/api/status':
            with ui_lock:
                elapsed = time.time() - ui_state["start_time"] if ui_state["start_time"] > 0 else 0
                data = {
                    "total": ui_state["total"],
                    "processed": ui_state["processed"],
                    "elapsed": elapsed,
                    "genre_counts": dict(ui_state["genre_counts"]),
                    "recent": list(reversed(ui_state["recent"][-100:])),
                    "workers": {str(k): v for k, v in ui_state["workers"].items()},
                    "running": ui_state["running"],
                    "cached": ui_state["unique_artists_cached"],
                    "searched": ui_state["unique_artists_searched"],
                }
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

def start_web_server():
    server = socketserver.ThreadingTCPServer(('0.0.0.0', WEB_UI_PORT), DashboardHandler)
    server.daemon_threads = True
    server.serve_forever()

# ============================================================
# WORKER
# ============================================================
def classification_worker(worker_id, q, local_artist_map, history_cache, csv_path, history_path, total_to_process, progress_counter):
    while True:
        try:
            item = q.get_nowait()
        except queue.Empty:
            with ui_lock:
                ui_state["workers"][worker_id] = {"artist": "— selesai —", "status": "idle", "count": ui_state["workers"].get(worker_id, {}).get("count", 0)}
            break

        row_idx, row_data = item
        artist = str(row_data.get('Nama Penyanyi', '')).strip()
        title = str(row_data.get('Judul Lagu', '')).strip()
        artist_lower = artist.lower().strip()

        # Update worker status
        with ui_lock:
            wc = ui_state["workers"].get(worker_id, {}).get("count", 0)
            ui_state["workers"][worker_id] = {"artist": artist[:30], "status": "active", "count": wc}

        genre = "Pop Indo"
        source = "Offline Fallback"

        if artist_lower in local_artist_map:
            genre = local_artist_map[artist_lower]
            source = "Local DB Lookup"
        elif artist_lower in history_cache:
            genre = history_cache[artist_lower]
            source = "JSON Cache"
            with ui_lock:
                ui_state["unique_artists_cached"] += 1
        else:
            genre = get_standardized_genre(artist)
            source = "Web Search"
            with json_write_lock:
                history_cache[artist_lower] = genre
                try:
                    with open(history_path, 'w', encoding='utf-8') as f:
                        json.dump(history_cache, f, indent=4)
                except Exception:
                    pass
            with ui_lock:
                ui_state["unique_artists_searched"] += 1
            time.sleep(random.uniform(0.3, 0.7))

        row_data['Kategori/Genre'] = genre

        with csv_write_lock:
            try:
                file_exists = os.path.exists(csv_path)
                with open(csv_path, 'a', encoding='utf-8', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=[
                        'Kategori/Genre', 'Nama Penyanyi', 'Judul Lagu', 'Status Download',
                        'Lokasi File', 'Ukuran File (MB)', 'Durasi', 'Tautan', 'Keterangan/Error'
                    ])
                    if not file_exists:
                        writer.writeheader()
                    writer.writerow(row_data)
            except Exception as e:
                with console_lock:
                    print(f"      [W{worker_id}] {colorama.Fore.RED}[Error] CSV: {e}{colorama.Style.RESET_ALL}")

        progress_counter[0] += 1
        pct = (progress_counter[0] / total_to_process) * 100

        # Update UI state
        with ui_lock:
            ui_state["processed"] = progress_counter[0]
            ui_state["genre_counts"][genre] += 1
            ui_state["recent"].append({"artist": artist[:30], "title": title[:40], "genre": genre, "source": source})
            if len(ui_state["recent"]) > 200:
                ui_state["recent"] = ui_state["recent"][-100:]
            wc = ui_state["workers"].get(worker_id, {}).get("count", 0)
            ui_state["workers"][worker_id] = {"artist": artist[:30], "status": "active", "count": wc + 1}

        with console_lock:
            try:
                print(f"  [{progress_counter[0]}/{total_to_process} | {pct:.1f}%] {colorama.Fore.CYAN}{artist[:22]}{colorama.Style.RESET_ALL} -> {colorama.Fore.GREEN}{genre}{colorama.Style.RESET_ALL} ({source})")
            except Exception:
                try:
                    clean_artist = re.sub(r'[^\x20-\x7E]+', '?', artist)
                    print(f"  [{progress_counter[0]}/{total_to_process} | {pct:.1f}%] {clean_artist[:22]} -> {genre} ({source})")
                except Exception:
                    pass

        q.task_done()

# ============================================================
# MAIN
# ============================================================
def main():
    bot_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(bot_dir)
    excel_path = os.path.join(parent_dir, "Database_Karaoke_Dimpi_2026.xlsx")
    excel_backup_path = os.path.join(parent_dir, "Database_Karaoke_Dimpi_2026.xlsx.bak")
    csv_path = os.path.join(bot_dir, "Database_Karaoke_Dimpi_2026_repaired.csv")
    xlsx_repaired_path = os.path.join(bot_dir, "Database_Karaoke_Dimpi_2026_repaired.xlsx")
    history_path = os.path.join(bot_dir, "genre_repair_history.json")

    print(f"{colorama.Fore.GREEN}=========================================================={colorama.Style.RESET_ALL}")
    print(f"    AUTOMATED GENRE RECONSTRUCTION BOT ({NUM_WORKERS} THREADS)")
    print(f"    Web UI Dashboard: http://localhost:{WEB_UI_PORT}")
    print(f"{colorama.Fore.GREEN}=========================================================={colorama.Style.RESET_ALL}")

    # Start web UI server
    web_thread = threading.Thread(target=start_web_server, daemon=True)
    web_thread.start()
    print(f" -> Web UI berjalan di {colorama.Fore.CYAN}http://localhost:{WEB_UI_PORT}{colorama.Style.RESET_ALL}")

    if not os.path.exists(excel_path):
        print(f" {colorama.Fore.RED}[Error] Berkas '{excel_path}' tidak ditemukan!{colorama.Style.RESET_ALL}")
        return

    # Check legacy CSV
    if os.path.exists(csv_path):
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                first_row = next(reader, None)
                if first_row:
                    cat = first_row.get('Kategori/Genre', '')
                    if cat in {"Indonesia", "Barat", "Malaysia", "Korea", "Jepang", "Mandarin"}:
                        os.remove(csv_path)
                        print(" -> Menemukan progress CSV lama (berkategori negara). Menghapusnya untuk mulai baru.")
                        if os.path.exists(history_path):
                            os.remove(history_path)
                            print(" -> Menghapus cache JSON lama untuk mulai baru.")
        except Exception as e:
            print(f" -> Gagal mengecek progress lama: {e}")

    print(" Memuat berkas Database_Karaoke_Dimpi_2026.xlsx...")
    df = pd.read_excel(excel_path)
    total_rows = len(df)
    print(f" -> Berhasil memuat {colorama.Fore.CYAN}{total_rows}{colorama.Style.RESET_ALL} baris lagu.")

    local_artist_map = {}
    print(" Penentuan cepat lokal dinonaktifkan (rombak ulang seluruh genre dari web/heuristik)...")

    history_cache = {}
    if os.path.exists(history_path):
        try:
            with open(history_path, 'r', encoding='utf-8') as f:
                history_cache = json.load(f)
            history_cache = {k: v for k, v in history_cache.items() if v in VALID_GENRES}
            print(f" -> Berhasil memuat status resume: {len(history_cache)} penyanyi dalam riwayat cache.")
        except Exception:
            pass

    processed_keys = set()
    if os.path.exists(csv_path):
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    art = str(row.get('Nama Penyanyi', '')).strip().lower()
                    tit = str(row.get('Judul Lagu', '')).strip().lower()
                    processed_keys.add((art, tit))
                    # Also count genre for UI
                    g = row.get('Kategori/Genre', '')
                    if g:
                        ui_state["genre_counts"][g] += 1
            print(f" -> Menemukan progress CSV sebelumnya: {colorama.Fore.GREEN}{len(processed_keys)}{colorama.Style.RESET_ALL} lagu sudah diproses.")
        except Exception as e:
            print(f" {colorama.Fore.RED}[Warning] Gagal membaca progress CSV: {e}{colorama.Style.RESET_ALL}")

    q = queue.Queue()
    queued_count = 0
    for idx, row in df.iterrows():
        art = str(row.get('Nama Penyanyi', '')).strip()
        tit = str(row.get('Judul Lagu', '')).strip()
        art_lower = art.lower().strip()
        tit_lower = tit.lower().strip()
        if (art_lower, tit_lower) in processed_keys:
            continue
        row_dict = {
            'Kategori/Genre': row.get('Kategori/Genre', ''),
            'Nama Penyanyi': art,
            'Judul Lagu': tit,
            'Status Download': row.get('Status Download', ''),
            'Lokasi File': row.get('Lokasi File', ''),
            'Ukuran File (MB)': row.get('Ukuran File (MB)', ''),
            'Durasi': row.get('Durasi', ''),
            'Tautan': row.get('Tautan', ''),
            'Keterangan/Error': row.get('Keterangan/Error', '')
        }
        q.put((idx, row_dict))
        queued_count += 1

    # Initialize UI state
    ui_state["total"] = queued_count + len(processed_keys)
    ui_state["processed"] = len(processed_keys)
    ui_state["start_time"] = time.time()

    print(f" -> Lagu yang perlu diproses/diperbaiki: {colorama.Fore.CYAN}{queued_count}{colorama.Style.RESET_ALL} baris.")

    if queued_count == 0:
        print(f"\n{colorama.Fore.GREEN} Semua lagu sudah selesai diproses di file CSV.{colorama.Style.RESET_ALL}")
    else:
        progress_counter = [len(processed_keys)]
        threads = []

        print(f" Memulai {NUM_WORKERS} worker threads paralel...")
        for i in range(NUM_WORKERS):
            ui_state["workers"][i + 1] = {"artist": "menunggu...", "status": "idle", "count": 0}
            t = threading.Thread(
                target=classification_worker,
                args=(i + 1, q, local_artist_map, history_cache, csv_path, history_path, ui_state["total"], progress_counter),
                daemon=True
            )
            t.start()
            threads.append(t)

        try:
            while not q.empty():
                time.sleep(1)
            q.join()
        except KeyboardInterrupt:
            print(f"\n{colorama.Fore.YELLOW} [Info] Deteksi interupsi (Ctrl+C). Menyimpan progress dan bersiap keluar...{colorama.Style.RESET_ALL}")
            ui_state["running"] = False
            return

    ui_state["running"] = False

    # Convert CSV to Excel
    print(f"\n{colorama.Fore.GREEN}=========================================================={colorama.Style.RESET_ALL}")
    print(" Mengonversi hasil CSV ke berkas Excel...")
    if os.path.exists(csv_path):
        try:
            if os.path.exists(excel_path) and not os.path.exists(excel_backup_path):
                shutil.copy2(excel_path, excel_backup_path)
                print(f" -> Berhasil mencadangkan Excel asli ke '{excel_backup_path}'")
            df_repaired = pd.read_csv(csv_path)
            df_repaired.sort_values(by=['Kategori/Genre', 'Nama Penyanyi', 'Judul Lagu'], inplace=True, ignore_index=True)
            df_repaired.to_excel(excel_path, index=False)
            print(f" -> {colorama.Fore.GREEN}Database utama diperbarui: {excel_path}{colorama.Style.RESET_ALL}")
            df_repaired.to_excel(xlsx_repaired_path, index=False)
            print(f" -> {colorama.Fore.GREEN}Salinan database disimpan di folder bot: {xlsx_repaired_path}{colorama.Style.RESET_ALL}")
        except Exception as e:
            print(f" {colorama.Fore.RED}[Error] Gagal menulis ke Excel: {e}{colorama.Style.RESET_ALL}")
    else:
        print(f" {colorama.Fore.YELLOW}[Warning] File CSV progress tidak ditemukan.{colorama.Style.RESET_ALL}")

    print(f"{colorama.Fore.GREEN}=========================================================={colorama.Style.RESET_ALL}\n")
    print(" Pekerjaan perbaikan selesai!")

if __name__ == "__main__":
    main()
