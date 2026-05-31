import urllib.request
import urllib.parse
import json
import re

INDONESIAN_WORDS = {
    'yang', 'dan', 'dengan', 'untuk', 'pada', 'ke', 'dari', 'dalam', 'ini', 'itu',
    'aku', 'kamu', 'dia', 'mereka', 'kita', 'kami', 'kau', 'mu', 'ku', 'nya',
    'cinta', 'hati', 'rasa', 'bisa', 'tidak', 'tak', 'jangan', 'akan', 'sudah',
    'selamat', 'pagi', 'siang', 'malam', 'hari', 'jalan', 'satu', 'dua', 'tiga',
    'kasih', 'sayang', 'rindu', 'kembali', 'pergi', 'datang', 'lihat', 'dengar',
    'suka', 'ingin', 'tahu', 'mau', 'ada', 'tiada', 'lagu', 'nyanyi', 'gitar',
    'kunci', 'lirik', 'sakit', 'senang', 'sedih', 'bahagia', 'selamanya', 'sampai',
    'mati', 'hidup', 'jiwa', 'raga', 'bintang', 'bulan', 'matahari', 'langit',
    'ojo', 'dibandingke', 'tresno', 'loro', 'ati', 'aku', 'kowe', 'siji', 'loro', 'telu' # Javanese common words
}

MALAYSIAN_ARTISTS = {
    'exists', 'slam', 'ukays', 'siti nurhaliza', 'amy search', 'search', 'wings', 
    'iklim', 'p. ramlee', 'yuna', 'saleem', 'tajul', 'spoon', 'spin', 'screen', 
    'lestari', 'eye', 'stings', 'mega', 'flophouse', 'insomniacks', 'masdo'
}

def clean_for_match(s):
    return re.sub(r'[^a-z0-9\s]', '', s.lower()).strip()

def is_indonesian_text(text):
    if not text:
        return False
    words = re.sub(r'[^a-z\s]', '', text.lower()).split()
    matched = sum(1 for w in words if w in INDONESIAN_WORDS)
    return matched >= 1

def query_itunes(artist, title):
    query = f"{artist} {title}"
    url = f"https://itunes.apple.com/search?term={urllib.parse.quote(query)}&limit=1&entity=musicTrack"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
            results = data.get('results', [])
            if results:
                return results[0]
    except Exception:
        pass
    
    # Fallback to artist only search
    url_art = f"https://itunes.apple.com/search?term={urllib.parse.quote(artist)}&limit=3&entity=musicTrack"
    req_art = urllib.request.Request(url_art, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req_art, timeout=8) as resp:
            data = json.loads(resp.read().decode())
            results = data.get('results', [])
            if results:
                return results[0]
    except Exception:
        pass
    return None

def classify_genre(artist, title, local_artist_map=None):
    artist_lower = artist.lower().strip()
    
    # 1. Local database lookup first
    if local_artist_map and artist_lower in local_artist_map:
        return local_artist_map[artist_lower]
        
    # 2. Check for Malaysian known artists
    if any(m_art in artist_lower for m_art in MALAYSIAN_ARTISTS):
        return "Malaysia"
        
    # 3. Query iTunes API
    track_info = query_itunes(artist, title)
    if track_info:
        genre_name = track_info.get('primaryGenreName', '').lower()
        
        if any(x in genre_name for x in ['dangdut', 'indo', 'indonesian']):
            return "Indonesia"
        if any(x in genre_name for x in ['k-pop', 'kpop', 'korean']):
            return "Korea"
        if any(x in genre_name for x in ['j-pop', 'jpop', 'japanese', 'anime']):
            return "Jepang"
        if any(x in genre_name for x in ['c-pop', 'cpop', 'mandopop', 'chinese', 'taiwanese', 'mandarin']):
            return "Mandarin"
        if any(x in genre_name for x in ['malay', 'malaysian']):
            return "Malaysia"
            
        # If it returns standard genres (pop, rock, metal, country) and contains non-Indo words
        if any(x in genre_name for x in ['pop', 'rock', 'metal', 'r&b', 'rap', 'hip hop', 'alternative', 'country', 'singer/songwriter']):
            # If the title or artist has Indonesian words, it's Indonesia
            if is_indonesian_text(artist) or is_indonesian_text(title):
                return "Indonesia"
            else:
                return "Barat"
                
    # 4. Offline Fallback Heuristics
    if is_indonesian_text(artist) or is_indonesian_text(title):
        return "Indonesia"
        
    # Check if mostly English words
    english_words = {'the', 'you', 'me', 'love', 'i', 'and', 'to', 'a', 'in', 'it', 'is', 'of', 'for', 'on', 'my', 'your', 'with', 'that', 'this'}
    words = re.sub(r'[^a-z\s]', '', title.lower() + " " + artist.lower()).split()
    if sum(1 for w in words if w in english_words) >= 1:
        return "Barat"
        
    # Default fallback
    return "Indonesia"

# Test
tests = [
    ("Abah Lala", "Ojo Dibandingke"),
    ("Taylor Swift", "Love Story"),
    ("Exists", "Mencari Alasan"),
    ("BTS", "Dynamite"),
    ("Yoasobi", "Idol"),
    ("Jay Chou", "Sunny Day"),
    ("Noah", "Separuh Aku"),
    ("Eny Sagita", "Gede Roso"),
    ("Siti Nurhaliza", "Cindai"),
]

for art, tit in tests:
    gen = classify_genre(art, tit)
    print(f"'{art}' - '{tit}' -> {gen}")
