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
    'ojo', 'dibandingke', 'tresno', 'loro', 'ati', 'aku', 'kowe', 'siji', 'loro', 'telu'
}

MALAYSIAN_ARTISTS = {
    'exists', 'slam', 'ukays', 'siti nurhaliza', 'amy search', 'search', 'wings', 
    'iklim', 'p. ramlee', 'yuna', 'saleem', 'tajul', 'spoon', 'spin', 'screen', 
    'lestari', 'eye', 'stings', 'mega', 'flophouse', 'insomniacks', 'masdo'
}

def is_indonesian_text(text):
    if not text:
        return False
    words = re.sub(r'[^a-z\s]', '', text.lower()).split()
    matched = sum(1 for w in words if w in INDONESIAN_WORDS)
    return matched >= 1

def query_wiki(query, lang='id'):
    encoded = urllib.parse.quote(query)
    url = f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search&srsearch={encoded}&format=json"
    req = urllib.request.Request(url, headers={'User-Agent': 'KaraokeGenreRepair/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            search_results = data.get('query', {}).get('search', [])
            if search_results:
                return " ".join([item.get('snippet', '') + " " + item.get('title', '') for item in search_results[:3]])
    except Exception:
        pass
    return ""

def query_itunes_info(artist):
    url = f"https://itunes.apple.com/search?term={urllib.parse.quote(artist)}&limit=3&entity=musicTrack"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            results = data.get('results', [])
            if results:
                genres = [r.get('primaryGenreName', '') for r in results]
                # Return most common genre name
                return genres[0] if genres else ""
    except Exception:
        pass
    return ""

def classify_artist_origin(artist):
    artist_lower = artist.lower().strip()
    
    if any(m_art in artist_lower for m_art in MALAYSIAN_ARTISTS):
        return "Malaysia"
        
    wiki_id = query_wiki(artist, "id").lower()
    if wiki_id:
        if any(x in wiki_id for x in ['malaysia', 'kuala lumpur', 'johor', 'selangor']):
            return "Malaysia"
        if any(x in wiki_id for x in ['korea', 'seoul', 'k-pop', 'kpop']):
            return "Korea"
        if any(x in wiki_id for x in ['jepang', 'tokyo', 'osaka', 'j-pop', 'jpop', 'anime']):
            return "Jepang"
        if any(x in wiki_id for x in ['tiongkok', 'china', 'cina', 'taiwan', 'hong kong', 'hongkong', 'mandarin', 'c-pop']):
            return "Mandarin"
        if any(x in wiki_id for x in ['amerika', 'inggris', 'serikat', 'london', 'new york', 'barat', 'kanada', 'australia', 'jerman', 'prancis']):
            return "Barat"
        if any(x in wiki_id for x in ['grup musik', 'grup band', 'penyanyi', 'musisi', 'dangdut', 'pedangdut', 'vokalis', 'lagu', 'album', 'boyolali', 'bandung', 'jakarta', 'yogyakarta', 'surabaya', 'semarang', 'medan', 'solo', 'koplo', 'campursari', 'pop']):
            return "Indonesia"
            
    wiki_en = query_wiki(artist, "en").lower()
    if wiki_en:
        if any(x in wiki_en for x in ['malaysian']):
            return "Malaysia"
        if any(x in wiki_en for x in ['japanese', 'j-pop', 'anime', 'japan']):
            return "Jepang"
        if any(x in wiki_en for x in ['korean', 'k-pop', 'seoul']):
            return "Korea"
        if any(x in wiki_en for x in ['chinese', 'taiwanese', 'mandarin', 'c-pop']):
            return "Mandarin"
        if any(x in wiki_en for x in ['indonesian']):
            return "Indonesia"
        if any(x in wiki_en for x in ['american', 'british', 'english', 'canadian', 'australian', 'german', 'french', 'uk', 'us', 'london']):
            return "Barat"
            
    if is_indonesian_text(artist):
        return "Indonesia"
        
    return "Barat"

def get_standardized_genre(artist):
    origin = classify_artist_origin(artist)
    style = query_itunes_info(artist).lower().strip()
    
    # If style is empty, try to check wiki snippet for genre clues
    if not style:
        wiki_id = query_wiki(artist, "id").lower()
        if 'dangdut' in wiki_id or 'koplo' in wiki_id or 'campursari' in wiki_id:
            style = 'dangdut'
        elif 'rock' in wiki_id or 'metal' in wiki_id:
            style = 'rock'
        else:
            style = 'pop'
            
    if origin == "Korea":
        return "K-Pop"
    if origin == "Jepang":
        return "J-Pop"
    if origin == "Mandarin":
        return "Mandopop"
        
    if origin == "Malaysia":
        if any(x in style for x in ['rock', 'metal', 'alternative']):
            return "Rock Melayu"
        return "Pop Melayu"
        
    if origin == "Indonesia":
        if any(x in style for x in ['dangdut', 'koplo', 'campursari', 'tarling']):
            return "Dangdut"
        if any(x in style for x in ['rock', 'metal', 'alternative', 'punk']):
            return "Rock Indo"
        return "Pop Indo"
        
    if origin == "Barat":
        if any(x in style for x in ['rock', 'metal', 'alternative', 'punk', 'grunge']):
            return "Rock Barat"
        if any(x in style for x in ['pop', 'r&b', 'singer/songwriter', 'dance', 'electronic', 'folk']):
            return "Pop Barat"
        if 'jazz' in style:
            return "Jazz"
        if 'reggae' in style:
            return "Reggae"
        if 'hip' in style or 'rap' in style:
            return "Hip Hop"
        return "Pop Barat"
        
    return "Pop Indo"

# Test
test_artists = [
    "Denny Caknan",
    "Taylor Swift",
    "Exists",
    "BLACKPINK",
    "LiSA",
    "Teresa Teng",
    "Peterpan",
    "Naff",
    "Sheila On 7",
    "Coldplay",
    "Jamrud",
    "Abah Lala"
]

for art in test_artists:
    print(f"Artist: {art:15} -> Standardized Genre: {get_standardized_genre(art)}")
