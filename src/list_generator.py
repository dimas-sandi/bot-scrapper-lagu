import os
import re
import json
import urllib.request
import urllib.parse
import yt_dlp
import colorama

colorama.init()

class SearchLogger(object):
    def debug(self, msg):
        pass
    def warning(self, msg):
        pass
    def error(self, msg):
        pass

# Top artists per genre to enable smart targeted search queries
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

def parse_video_title(video_title, channel_name):
    """
    Cleans and parses a YouTube video title into (Artist, Title).
    Uses regex rules tailored for karaoke video titles.
    """
    cleaned = video_title
    
    # 1. Remove text inside parentheses () or brackets []
    cleaned = re.sub(r'[\(\[][^\]\)]*[\)\]]', '', cleaned)
    
    # 2. Remove common promotional, quality, and karaoke metadata keywords
    words_to_remove = [
        r'\bkaraoke\b', r'\binstrumental\b', r'\btanpa vokal\b', r'\btanpa vocal\b',
        r'\bno vocal\s*s?\b', r'\boff vocal\b', r'\bminus one\b', r'\bversion\b',
        r'\bcover\b', r'\blirik\b', r'\blyrics\b', r'\bofficial\b', r'\bvideo\b',
        r'\baudio\b', r'\bhd\b', r'\bhq\b', r'\b1080p\b', r'\b720p\b', r'\bterbaru\b',
        r'\bpop\b', r'\brock\b', r'\bdangdut\b', r'\bkoplo\b', r'\blagu\b', r'\btempo\b',
        r'\bada vokal\b', r'\bplus vokal\b', r'\bno vocals\b', r'\boff-vocal\b'
    ]
    for word in words_to_remove:
        cleaned = re.sub(word, '', cleaned, flags=re.IGNORECASE)
        
    # Remove hashtags and trailing/leading spaces
    cleaned = re.sub(r'#\S+', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    # 3. Split by common separators (-, |, ~, :)
    # Prefer splitting by dash with spaces around it to protect words like Tipe-X, Blink-182
    parts = []
    if re.search(r'\s+-\s+', cleaned):
        parts = [p.strip() for p in re.split(r'\s+-\s+', cleaned) if p.strip()]
    else:
        # Try other separators
        separators = [r'\s*\|\s*', r'\s*~\s*', r'\s*:\s*', r'\s*-\s*']
        for sep in separators:
            split_parts = re.split(sep, cleaned)
            if len(split_parts) >= 2:
                parts = [p.strip() for p in split_parts if p.strip()]
                break
                
    # Smart merge for badly split compound band names (like Tipe-X, Blink-182)
    if len(parts) >= 2:
        i = 0
        while i < len(parts) - 1:
            p1 = parts[i].lower()
            p2 = parts[i+1].lower()
            # If we split something like "Tipe" and "X", or "X" as a second part, merge them back
            if (p1 == "tipe" and p2 == "x") or (p2 == "x" and len(p1) > 0) or (len(p2) == 1 and p2.isalnum() and not p2.isdigit()):
                parts[i] = f"{parts[i]}-{parts[i+1]}"
                parts.pop(i+1)
            else:
                i += 1
            
    # If we have 3 or more parts, check if the first part is a genre or karaoke indicator
    if len(parts) >= 3:
        genre_kws = ['karaoke', 'dangdut', 'jawa', 'pop', 'rock', 'barat', 'indonesia', 'koplo', 'acoustic', 'akustik', 'jepang', 'korea', 'mandarin', 'malaysia']
        if parts[0].lower() in genre_kws or len(parts[0]) <= 4:
            parts.pop(0)
            
    artist = "Penyanyi Tidak Dikenal"
    title = cleaned
    
    if len(parts) >= 2:
        part1 = parts[0]
        part2 = parts[1]
        
        part1 = re.sub(r'\s+', ' ', part1).strip()
        part2 = re.sub(r'\s+', ' ', part2).strip()
        
        # Check if swapped (Title - Artist instead of Artist - Title)
        is_swapped = False
        part1_lower = part1.lower()
        part2_lower = part2.lower()
        
        # Flatten all top artists
        all_top_artists_lower = set()
        for art_list in TOP_ARTISTS.values():
            for art_name in art_list:
                all_top_artists_lower.add(art_name.lower())
                
        # If part2 is in top artists but part1 is not
        if part2_lower in all_top_artists_lower and part1_lower not in all_top_artists_lower:
            is_swapped = True
        elif part1_lower in all_top_artists_lower and part2_lower in all_top_artists_lower:
            is_swapped = False
        else:
            # Check channel name
            if channel_name:
                chan_lower = channel_name.lower()
                part1_in_chan = (part1_lower in chan_lower) or (chan_lower in part1_lower)
                part2_in_chan = (part2_lower in chan_lower) or (chan_lower in part2_lower)
                if part2_in_chan and not part1_in_chan:
                    generic_channels = ['karaoke', 'instrumental', 'sing', 'king', 'music', 'studio', 'cover', 'official', 'acoustic', 'akustik', 'channel', 'tv']
                    is_chan_generic = any(g in chan_lower for g in generic_channels)
                    if not is_chan_generic:
                        is_swapped = True
                        
        if is_swapped:
            artist = part2
            title = part1
        else:
            artist = part1
            title = part2
    else:
        # Fallback: if no separator, try to use channel name as artist, unless it's a generic channel
        generic_channels = ['karaoke', 'instrumental', 'sing', 'king', 'music', 'studio', 'cover', 'official', 'acoustic', 'akustik', 'channel', 'tv']
        is_generic = False
        if channel_name:
            is_generic = any(g in channel_name.lower() for g in generic_channels)
            
        if channel_name and not is_generic:
            artist = channel_name.strip()
            title = cleaned
            
    artist = artist.title()
    title = title.title()
    
    if not artist or artist.lower() == 'nan':
        artist = "Penyanyi Tidak Dikenal"
    if not title or title.lower() == 'nan':
        title = "Judul Tidak Dikenal"
        
    return artist, title

def is_suspicious_entry(artist, title):
    """
    Checks if a parsed song entry (artist, title) looks suspicious
    and needs online validation.
    """
    artist_clean = artist.strip()
    title_clean = title.strip()
    
    if not artist_clean or not title_clean:
        return True
        
    # Short names check with exception for famous short names (e.g. BTS, IU, IVE, MAC, GEM)
    known_short_artists = {"bts", "iu", "ive", "mac", "gem", "lbi", "j.y", "exo", "txt", "nct", "cl"}
    if len(artist_clean) <= 3 and artist_clean.lower() not in known_short_artists:
        return True
        
    if len(title_clean) <= 2:
        return True
        
    if artist_clean.lower() == title_clean.lower():
        return True
        
    garbage_kws = {"karaoke", "instrumental", "vocal", "lyrics", "lirik", "official", "video", "download", "cover", "unknown", "tidak dikenal"}
    for kw in garbage_kws:
        if kw in artist_clean.lower() or kw in title_clean.lower():
            return True
            
    if not any(c.isalpha() for c in artist_clean) or not any(c.isalpha() for c in title_clean):
        return True
        
    return False

LAST_SEARCH_HAD_ERROR = False

def validate_song_online(artist, title):
    """
    Performs selective online verification via DuckDuckGo HTML search.
    Checks if the artist and song combination is valid.
    """
    global LAST_SEARCH_HAD_ERROR
    LAST_SEARCH_HAD_ERROR = False
    
    artist_clean = artist.strip()
    title_clean = title.strip()
    
    # Fast drop for clear single-character trash artists
    trash_artists = {"x", "y", "z", "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m", "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "tipe"}
    if artist_clean.lower() in trash_artists:
        return artist_clean, title_clean, False
        
    try:
        query = f'"{artist_clean}" "{title_clean}"'
        encoded_query = urllib.parse.quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
        
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        )
        
        with urllib.request.urlopen(req, timeout=5) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            
        if "No results found" in html or "tidak ditemukan hasil" in html:
            query_broad = f"{artist_clean} {title_clean} song"
            encoded_query_broad = urllib.parse.quote_plus(query_broad)
            url_broad = f"https://html.duckduckgo.com/html/?q={encoded_query_broad}"
            
            req_broad = urllib.request.Request(
                url_broad,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
            )
            with urllib.request.urlopen(req_broad, timeout=5) as resp_broad:
                html = resp_broad.read().decode('utf-8', errors='ignore')
                
        snippets = re.findall(r'<a class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
        titles = re.findall(r'<a class="result__url"[^>]*>(.*?)</a>', html, re.DOTALL)
        
        combined = (" ".join(snippets) + " " + " ".join(titles)).lower()
        combined = re.sub(r'<[^>]+>', ' ', combined)
        
        artist_words = [w.lower() for w in re.findall(r'\w+', artist_clean) if len(w) > 1]
        title_words = [w.lower() for w in re.findall(r'\w+', title_clean) if len(w) > 1]
        
        artist_ok = any(w in combined for w in artist_words) if artist_words else False
        title_ok = any(w in combined for w in title_words) if title_words else False
        
        if artist_ok and title_ok:
            return artist_clean, title_clean, True
            
        if artist_clean.lower() == "tipe" and "tipe-x" in combined:
            return "Tipe-X", title_clean, True
            
    except Exception as e:
        # Fallback to True to avoid losing valid songs due to temporary network failure
        LAST_SEARCH_HAD_ERROR = True
        import sys
        if len(sys.argv) > 0 and "test_validation" in sys.argv[0]:
            print(f"    (Debug: Koneksi bermasalah: {e})")
        return artist_clean, title_clean, True
        
    return artist_clean, title_clean, False

def extract_songs_from_web_text(text):
    """
    Parses plain text from web scrapers/blogs to extract song titles and artists.
    Looks for lines containing 'Artist - Song' or similar patterns.
    """
    # Remove HTML tags
    text_clean = re.sub(r'<[^>]+>', '\n', text)
    
    # Match patterns like: "1. Artist - Title" or "Artist - Title"
    pattern = r'(?:^|\n)\s*(?:\d+[\.\)]?\s*)?([^-\n\t|–—]{3,50})\s*[-–—|]\s*([^-\n\t|–—\(\[\r]{3,50})'
    matches = re.findall(pattern, text_clean)
    
    songs = []
    for match in matches:
        part1 = match[0].strip()
        part2 = match[1].strip()
        
        # Clean bracket metadata
        part1 = re.sub(r'[\(\[][^\]\)]*[\)\]]', '', part1).strip()
        part2 = re.sub(r'[\(\[][^\]\)]*[\)\]]', '', part2).strip()
        
        # Skip if either is too short or generic
        if len(part1) < 3 or len(part2) < 3:
            continue
            
        # Ignore common webpage navigation/header keywords
        ignore_kws = ['download', 'lirik', 'lagu', 'mp3', 'chord', 'kunci', 'gitar', 'album', 'terpopuler', 'hits', 'video', 'music']
        if any(w in part1.lower() for w in ignore_kws) or any(w in part2.lower() for w in ignore_kws):
            continue
            
        songs.append((part1, part2))
    return songs

def scrape_popular_songs_from_web(genre_name, year_val):
    """
    Scrapes DuckDuckGo HTML search results for the given genre and year to find
    popular song lists mentioned in result snippets and metadata.
    """
    songs = []
    try:
        query = f"daftar lagu {genre_name} terpopuler {year_val}"
        encoded_query = urllib.parse.quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
        
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        )
        
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            
        # Extract snippets from DuckDuckGo HTML
        snippets = re.findall(r'<a class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
        
        for snip in snippets:
            # Clean HTML entities
            snip_text = snip.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&#x27;', "'").replace('&quot;', '"')
            extracted = extract_songs_from_web_text(snip_text)
            songs.extend(extracted)
            
    except Exception:
        pass
    return list(set(songs))

def verify_and_get_karaoke_link(artist, title, ydl_opts):
    """
    Searches YouTube for a specific song to verify if a valid karaoke version exists.
    Returns (uploader, video_title) if a high scoring karaoke match is found, else None.
    """
    # Score function similar to downloader
    def score_title(t):
        t_l = t.lower()
        score = 0
        has_pos = False
        
        # Super Positives
        sp = ['no vocal', 'no vocals', 'tanpa vokal', 'tanpa vocal', 'off vocal', 'minus one', 'instrumental']
        for kw in sp:
            if kw in t_l:
                score += 35
                has_pos = True
                
        # Positives
        pos = ['karaoke', 'instrumental version', 'karaoke version']
        for kw in pos:
            if kw in t_l:
                score += 20
                has_pos = True
                
        # Hard Negatives
        neg = ['with vocal', 'with vocals', 'dengan vokal', 'dengan vocal', 'ada vokal', 'ada vocal', 'vocal only', 'vocal version', 'plus vocal']
        for kw in neg:
            if kw in t_l:
                score -= 45
                
        # Relevance
        if artist.lower() in t_l:
            score += 15
        if title.lower() in t_l:
            score += 15
            
        return score if has_pos else -10

    query = f"{artist} {title} karaoke no vocal"
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            res = ydl.extract_info(f"ytsearch3:{query}", download=False)
            if res and 'entries' in res:
                for entry in res['entries']:
                    score = score_title(entry.get('title', ''))
                    if score > 15: # Good match found
                        return entry.get('uploader', ''), entry.get('title', '')
    except Exception:
        pass
    return None
