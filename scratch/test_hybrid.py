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

def clean_for_match(s):
    return re.sub(r'[^a-z0-9\s]', '', s.lower()).strip()

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

def query_itunes_genre(artist):
    url = f"https://itunes.apple.com/search?term={urllib.parse.quote(artist)}&limit=3&entity=musicTrack"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            results = data.get('results', [])
            if results:
                return [r.get('primaryGenreName', '') for r in results]
    except Exception:
        pass
    return []

def classify_artist(artist):
    artist_lower = artist.lower().strip()
    
    # 1. Check Malaysian known artists list
    if any(m_art in artist_lower for m_art in MALAYSIAN_ARTISTS):
        return "Malaysia"
        
    # 2. Query Wikipedia ID
    wiki_id = query_wiki(artist, "id").lower()
    if wiki_id:
        if any(x in wiki_id for x in ['dangdut', 'pedangdut', 'campursari', 'koplo', 'jawa', 'sunda', 'indonesia', 'kelahiran boyolali']):
            return "Indonesia"
        if any(x in wiki_id for x in ['malaysia', 'kuala lumpur', 'johor']):
            return "Malaysia"
        if any(x in wiki_id for x in ['korea', 'seoul', 'k-pop', 'kpop']):
            return "Korea"
        if any(x in wiki_id for x in ['jepang', 'tokyo', 'osaka', 'j-pop', 'jpop', 'anime']):
            return "Jepang"
        if any(x in wiki_id for x in ['tiongkok', 'cina', 'taiwan', 'hong kong', 'mandarin', 'c-pop']):
            return "Mandarin"
        if any(x in wiki_id for x in ['amerika', 'inggris', 'us', 'uk', 'london', 'new york', 'barat']):
            return "Barat"
            
    # 3. Query Wikipedia EN
    wiki_en = query_wiki(artist, "en").lower()
    if wiki_en:
        if any(x in wiki_en for x in ['indonesian']):
            return "Indonesia"
        if any(x in wiki_en for x in ['malaysian']):
            return "Malaysia"
        if any(x in wiki_en for x in ['japanese', 'j-pop', 'anime']):
            return "Jepang"
        if any(x in wiki_en for x in ['korean', 'k-pop', 'seoul']):
            return "Korea"
        if any(x in wiki_en for x in ['chinese', 'taiwanese', 'mandarin', 'c-pop']):
            return "Mandarin"
        if any(x in wiki_en for x in ['american', 'british', 'english', 'canadian', 'australian', 'german', 'french', 'uk', 'us', 'london']):
            return "Barat"

    # 4. Query iTunes
    genres = [g.lower() for g in query_itunes_genre(artist)]
    if genres:
        joined_genres = " ".join(genres)
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

    # 5. Offline Fallback Heuristics
    if is_indonesian_text(artist):
        return "Indonesia"
        
    # Check for English words
    english_words = {'the', 'you', 'me', 'love', 'i', 'and', 'to', 'a', 'in', 'it', 'is', 'of', 'for', 'on', 'my', 'your', 'with', 'that', 'this'}
    words = re.sub(r'[^a-z\s]', '', artist.lower()).split()
    if sum(1 for w in words if w in english_words) >= 1:
        return "Barat"
        
    return "Indonesia"

# Test cases
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
]

for art in test_artists:
    print(f"Artist: {art} -> Genre: {classify_artist(art)}")
