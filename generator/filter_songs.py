import os
import sys
import re
import csv
import json
import urllib.request
import urllib.parse
import time
import colorama
import pandas as pd
from tqdm import tqdm

colorama.init()

# List of typical compilation/medley/non-stop keywords (local filter)
COMPILATION_KEYWORDS = [
    r'\bkompilasi\b', r'\bcompilation\b', r'\bmedley\b', r'\bnonstop\b', r'\bnon\s+stop\b',
    r'\bmashup\b', r'\bmegamix\b', r'\bfull\s+album\b', r'\bbest\s+of\b', r'\bgreatest\s+hits\b',
    r'\bplaylist\b', r'\bmix\b', r'\btop\s+hits\b', r'\bkumpulan\b', r'\balbum\s+lengkap\b',
    r'\bpilihan\s+terbaik\b', r'\ball\s+songs\b', r'\bkaraoke\s+compilation\b',
    r'\bkaraoke\s+medley\b', r'\bkaraoke\s+non\s*stop\b', r'\bcover\s+kumpulan\b',
    r'\bkolaborasi\b', r'\bduet\s+full\b', r'\bslow\s+rock\s+terpopuler\b',
    r'\btembang\s+kenangan\b', r'\bsad\s+songs\b', r'\btiktok\s+viral\b', r'\bviral\s+hits\b'
]

# Cache to store DuckDuckGo search results and avoid repeated queries
CACHE_FILE = "filter_cache.json"

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_cache(cache):
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f" (Gagal menyimpan cache: {e})")

def clean_name(name):
    """Basic cleaning for query and matching purposes."""
    if not name or name.lower() == 'nan':
        return ""
    name = re.sub(r'[\(\[][^\]\)]*[\)\]]', '', name) # Remove text in brackets
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def is_local_compilation(artist, title):
    """Heuristic check for compilation keywords in artist or title."""
    full_text = f"{artist} {title}".lower()
    for kw in COMPILATION_KEYWORDS:
        if re.search(kw, full_text):
            return True, kw
    
    # Generic title checks
    if re.search(r'^(top|daftar|kumpulan|lagu)\s+\d+', title.lower()):
        return True, "generic list pattern"
        
    return False, None

def search_duckduckgo(artist, title):
    """Performs a DuckDuckGo search and returns raw HTML."""
    query = f'"{artist}" "{title}"'
    encoded_query = urllib.parse.quote_plus(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            return html
    except Exception as e:
        # Retry with broader query if quoted query fails or times out
        query_broad = f"{artist} {title} song"
        encoded_query_broad = urllib.parse.quote_plus(query_broad)
        url_broad = f"https://html.duckduckgo.com/html/?q={encoded_query_broad}"
        req_broad = urllib.request.Request(url_broad, headers=headers)
        try:
            with urllib.request.urlopen(req_broad, timeout=8) as resp_broad:
                return resp_broad.read().decode('utf-8', errors='ignore')
        except Exception:
            return ""

def parse_search_results(html):
    """Extracts page titles and snippets from DDG HTML."""
    if not html:
        return [], []
    
    # Clean HTML entities
    html = html.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&#x27;', "'").replace('&quot;', '"')
    
    # Extract titles and snippets using regex
    titles = re.findall(r'<a class="result__url"[^>]*>(.*?)</a>', html, re.DOTALL)
    snippets = re.findall(r'<a class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
    
    # Clean tags from titles and snippets
    clean_titles = [re.sub(r'<[^>]+>', '', t).strip() for t in titles]
    clean_snippets = [re.sub(r'<[^>]+>', '', s).strip() for s in snippets]
    
    return clean_titles, clean_snippets

def correct_metadata_from_web(artist, title, year, search_titles, search_snippets):
    """
    Analyzes search results to:
    1. Confirm if the song is real (not compilation/fake)
    2. Correct the spelling/casing of Artist and Title
    3. Detect if Artist and Title are swapped
    4. Detect and correct the Release Year
    """
    artist_clean = clean_name(artist)
    title_clean = clean_name(title)
    
    if not artist_clean or not title_clean:
        return artist, title, year, False, "Missing info"
        
    combined_results = " | ".join(search_titles + search_snippets)
    combined_results_lower = combined_results.lower()
    
    # 1. Compilation/Medley verification from web contents
    web_compilation_kws = ["compilation", "kompilasi", "medley", "nonstop", "non-stop", "full album", "dj mix"]
    kw_hits = [kw for kw in web_compilation_kws if kw in combined_results_lower]
    # If the search results heavily mention compilation terms compared to the single terms
    if len(kw_hits) >= 2:
        return artist, title, year, False, f"Web compilation hits: {', '.join(kw_hits)}"
        
    # Check if we got any actual results
    if not search_titles:
        # No results at all might mean a fake or very obscure song title (e.g. search garbage)
        return artist, title, year, False, "No search results found"

    # 2. Year correction logic
    # Find all 4-digit years between 1950 and 2026
    found_years = re.findall(r'\b(19[5-9]\d|20[0-2]\d)\b', combined_results)
    
    # High-confidence year patterns in snippets
    confident_years = []
    year_patterns = [
        r'(?:released in|dirilis pada tahun|rilis tahun|tahun rilis|single rilis|release date)\s*:?\s*\b(19[5-9]\d|20[0-2]\d)\b',
        r'\b(19[5-9]\d|20[0-2]\d)\b\s*(?:single|album|song|released|dirilis|lirik)'
    ]
    for pattern in year_patterns:
        matches = re.findall(pattern, combined_results_lower)
        if matches:
            confident_years.extend(matches)
            
    corrected_year = year
    if confident_years:
        # Use the most frequent high-confidence year
        year_counts = {}
        for y in confident_years:
            year_counts[y] = year_counts.get(y, 0) + 1
        best_year = int(max(year_counts, key=year_counts.get))
        if best_year != year:
            corrected_year = best_year
    elif found_years:
        # Fallback to most common 4-digit year in search results
        year_counts = {}
        for y in found_years:
            year_counts[y] = year_counts.get(y, 0) + 1
        # Filter out years that occur only once if there are others
        best_year = int(max(year_counts, key=year_counts.get))
        if best_year != year:
            corrected_year = best_year

    # 3. Swap and Casing Correction
    # We look for structured titles in the search results like "Artist - Title" or "Title - Artist"
    # E.g. "Tiara Andini - Usai Lyrics | Genius Lyrics"
    corrected_artist = artist
    corrected_title = title
    swap_votes = 0
    normal_votes = 0
    
    # Flatten names for comparison
    art_words = set(re.findall(r'\w+', artist_clean.lower()))
    tit_words = set(re.findall(r'\w+', title_clean.lower()))
    
    for page_title in search_titles:
        # Standardize separators
        clean_page_title = re.sub(r'\s*[\-–—|]\s*', ' - ', page_title)
        parts = clean_page_title.split(' - ')
        if len(parts) >= 2:
            part1 = parts[0].strip()
            part2 = parts[1].strip()
            
            p1_words = set(re.findall(r'\w+', part1.lower()))
            p2_words = set(re.findall(r'\w+', part2.lower()))
            
            # Check if part1 matches title and part2 matches artist (Swapped)
            p1_is_title = len(tit_words.intersection(p1_words)) >= min(len(tit_words), 2)
            p2_is_artist = len(art_words.intersection(p2_words)) >= min(len(art_words), 2)
            
            # Check if part1 matches artist and part2 matches title (Normal)
            p1_is_artist = len(art_words.intersection(p1_words)) >= min(len(art_words), 2)
            p2_is_title = len(tit_words.intersection(p2_words)) >= min(len(tit_words), 2)
            
            if p1_is_title and p2_is_artist and not (p1_is_artist and p2_is_title):
                swap_votes += 1
                # Grab corrected spellings from page title
                if len(part2) < len(corrected_artist) * 1.5 and len(part2) > 2:
                    corrected_artist = part2
                if len(part1) < len(corrected_title) * 1.5 and len(part1) > 2:
                    corrected_title = part1
            elif p1_is_artist and p2_is_title and not (p1_is_title and p2_is_artist):
                normal_votes += 1
                if len(part1) < len(corrected_artist) * 1.5 and len(part1) > 2:
                    corrected_artist = part1
                if len(part2) < len(corrected_title) * 1.5 and len(part2) > 2:
                    corrected_title = part2

    # Perform swap if votes favor swap
    is_swapped = False
    if swap_votes > normal_votes and swap_votes >= 1:
        corrected_artist, corrected_title = corrected_title, corrected_artist
        is_swapped = True

    # 4. Final cleaning and formatting
    # Remove junk characters like parentheses/brackets from corrected names
    corrected_artist = clean_name(corrected_artist).title()
    corrected_title = clean_name(corrected_title).title()
    
    # Capitalization adjustments for special band names/acronyms
    def adjust_casing(name):
        words = name.split()
        adjusted = []
        for w in words:
            if w.lower() in ['bts', 'iu', 'ive', 'mac', 'gem', 'lbi', 'exo', 'txt', 'nct']:
                adjusted.append(w.upper())
            elif '-' in w:
                # e.g. Tipe-X
                parts = w.split('-')
                adjusted.append('-'.join([p.capitalize() for p in parts]))
            else:
                adjusted.append(w)
        return ' '.join(adjusted)
        
    corrected_artist = adjust_casing(corrected_artist)
    corrected_title = adjust_casing(corrected_title)
    
    # Ensure they are valid names
    if not corrected_artist or corrected_artist.lower() == 'nan':
        corrected_artist = artist.title()
    if not corrected_title or corrected_title.lower() == 'nan':
        corrected_title = title.title()
        
    return corrected_artist, corrected_title, corrected_year, True, "Verified & Corrected"

def get_file_list(proj_dir):
    """Scans directory for generated song list files and returns them."""
    files = []
    for f in os.listdir(proj_dir):
        if f.startswith("list lagu new") and f.endswith(".xlsx") and "rev" not in f:
            files.append(f)
    return sorted(files)

def main():
    proj_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(proj_dir)
    
    print(f"{colorama.Fore.CYAN}=========================================================={colorama.Style.RESET_ALL}")
    print(f"            SONG LIST FILTER & CORRECTION BOT             ")
    print(f"{colorama.Fore.CYAN}=========================================================={colorama.Style.RESET_ALL}")
    
    # 1. Select Input File
    excel_files = get_file_list(proj_dir)
    if not excel_files:
        print(f"{colorama.Fore.RED} [Error] Tidak ditemukan file 'list lagu new [Tahun].xlsx' di folder generator.{colorama.Style.RESET_ALL}")
        print(" Silakan jalankan generator terlebih dahulu untuk membuat daftar lagu.")
        sys.exit(1)
        
    print("\n File hasil generator yang terdeteksi:")
    for idx, f in enumerate(excel_files):
        print(f" [{idx + 1}] {f}")
        
    choice = input(f" Pilih file untuk difilter (1-{len(excel_files)}, default 1): ").strip()
    if choice.isdigit() and 1 <= int(choice) <= len(excel_files):
        selected_file = excel_files[int(choice) - 1]
    else:
        selected_file = excel_files[0]
        
    input_path = os.path.join(proj_dir, selected_file)
    print(f" -> Memilih file: {colorama.Fore.GREEN}{selected_file}{colorama.Style.RESET_ALL}")
    
    # Extract years range from filename
    # e.g. "list lagu new 2020-2026.xlsx" -> "2020-2026"
    years_match = re.search(r'list lagu new\s+(.+)\.xlsx', selected_file)
    if years_match:
        years_suffix = years_match.group(1).strip()
    else:
        years_suffix = "all"
        
    # Define output paths
    csv_output_name = f"list lagu new rev {years_suffix}.csv"
    xlsx_output_name = f"list lagu new rev final {years_suffix}.xlsx"
    csv_output_path = os.path.join(proj_dir, csv_output_name)
    xlsx_output_path = os.path.join(proj_dir, xlsx_output_name)
    
    # 2. Read Input Data
    try:
        df = pd.read_excel(input_path)
        print(f" -> Berhasil membaca {colorama.Fore.GREEN}{len(df)}{colorama.Style.RESET_ALL} lagu dari excel.")
    except Exception as e:
        print(f"{colorama.Fore.RED} [Error] Gagal membaca file excel: {e}{colorama.Style.RESET_ALL}")
        sys.exit(1)
        
    if df.empty or 'Nama Penyanyi' not in df.columns or 'Judul Lagu' not in df.columns:
        print(f"{colorama.Fore.RED} [Error] Format kolom file excel tidak sesuai (harus ada 'Nama Penyanyi' & 'Judul Lagu').{colorama.Style.RESET_ALL}")
        sys.exit(1)
        
    # Ask correction mode
    print(f"\n{colorama.Fore.CYAN}Pilih Opsi Verifikasi & Koreksi Online:{colorama.Style.RESET_ALL}")
    print(" [1] Heuristik Cepat & Verifikasi Online Selektif (Cepat & Direkomendasikan)")
    print("     -> Hanya lagu mencurigakan / terbalik yang di-search di Google/DDG.")
    print(" [2] Deep Online Search & Correction (Sangat Akurat tapi Butuh Waktu)")
    print("     -> Cari semua lagu di Google/DDG untuk verifikasi tahun, ejaan, & penulisan.")
    mode_choice = input(" Pilih mode (1/2, default 1): ").strip()
    deep_mode = (mode_choice == "2")
    
    # Load Cache
    cache = load_cache()
    print(f" -> Cache lokal memuat {len(cache)} hasil pencarian sebelumnya.")
    
    # Lists to store final results
    filtered_songs = []
    
    # Statistics counters
    stats = {
        'total_in': len(df),
        'deleted_local_compilation': 0,
        'deleted_online_compilation': 0,
        'deleted_not_found': 0,
        'swapped_corrected': 0,
        'spelling_corrected': 0,
        'year_corrected': 0,
        'kept_clean': 0
    }
    
    # 3. Processing Loop with beautiful progress bar
    print(f"\n Memulai pemrosesan lagu...")
    
    # Track seen key to avoid duplicates in the final output
    seen_final_songs = set()
    
    for idx, row in tqdm(df.iterrows(), total=len(df), desc="Filtering Songs", unit="song"):
        artist = str(row.get('Nama Penyanyi', '')).strip()
        title = str(row.get('Judul Lagu', '')).strip()
        genre = str(row.get('Kategori', '')).strip()
        
        try:
            year = int(row.get('Tahun', 0))
        except ValueError:
            year = 0
            
        if not artist or not title or artist.lower() == 'nan' or title.lower() == 'nan':
            continue
            
        # A. Local Heuristic check for compilation/medley
        is_comp, reason = is_local_compilation(artist, title)
        if is_comp:
            stats['deleted_local_compilation'] += 1
            # Skip compilation songs immediately
            continue
            
        # Determine if online check is needed
        # Mode 1: Selective (only suspicious, short names, possible swaps, or unknown years)
        # Mode 2: Deep (all songs)
        needs_online_check = deep_mode or year == 0 or len(artist) <= 3 or len(title) <= 3 or '-' in title or '(' in title or '[' in title or 'feat' in artist.lower() or 'with' in artist.lower()
        
        corrected_art = artist
        corrected_tit = title
        corrected_year = year
        is_valid = True
        
        if needs_online_check:
            cache_key = f"{artist.lower().strip()} - {title.lower().strip()}"
            
            if cache_key in cache:
                cached_data = cache[cache_key]
                corrected_art = cached_data.get('artist', artist)
                corrected_tit = cached_data.get('title', title)
                corrected_year = cached_data.get('year', year)
                is_valid = cached_data.get('is_valid', True)
                reason = cached_data.get('reason', '')
            else:
                # Call search
                html = search_duckduckgo(artist, title)
                search_titles, search_snippets = parse_search_results(html)
                
                # Run intelligent correction
                corrected_art, corrected_tit, corrected_year, is_valid, reason = correct_metadata_from_web(
                    artist, title, year, search_titles, search_snippets
                )
                
                # Save to cache
                cache[cache_key] = {
                    'artist': corrected_art,
                    'title': corrected_tit,
                    'year': corrected_year,
                    'is_valid': is_valid,
                    'reason': reason
                }
                
                # Slow down to respect DuckDuckGo terms
                time.sleep(1.0)
                
            if not is_valid:
                if "compilation" in reason.lower() or "mix" in reason.lower():
                    stats['deleted_online_compilation'] += 1
                else:
                    stats['deleted_not_found'] += 1
                continue
                
            # Log changes and track stats
            if corrected_art.lower() != artist.lower() or corrected_tit.lower() != title.lower():
                # Check if it was a swap
                if corrected_art.lower() == title.lower() and corrected_tit.lower() == artist.lower():
                    stats['swapped_corrected'] += 1
                else:
                    stats['spelling_corrected'] += 1
                    
            if corrected_year != year and corrected_year != 0:
                stats['year_corrected'] += 1
        
        # Deduplication check
        dup_key = f"{corrected_art.lower()} - {corrected_tit.lower()}"
        if dup_key in seen_final_songs:
            continue
            
        seen_final_songs.add(dup_key)
        stats['kept_clean'] += 1
        
        filtered_songs.append({
            'Nama Penyanyi': corrected_art,
            'Judul Lagu': corrected_tit,
            'Kategori': genre,
            'Tahun': corrected_year if corrected_year != 0 else year
        })
        
    # Save cache
    save_cache(cache)
    
    # 4. Save CSV Output
    fieldnames = ['Nama Penyanyi', 'Judul Lagu', 'Kategori', 'Tahun']
    try:
        with open(csv_output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for s in filtered_songs:
                writer.writerow(s)
        print(f"\n -> Berhasil menyimpan file CSV revisi: {colorama.Fore.GREEN}{csv_output_name}{colorama.Style.RESET_ALL}")
    except Exception as e:
        print(f"{colorama.Fore.RED} [Error] Gagal menulis file CSV: {e}{colorama.Style.RESET_ALL}")
        
    # 5. Compile and Save Sorted XLSX Output
    try:
        final_df = pd.DataFrame(filtered_songs)
        if not final_df.empty:
            final_df.sort_values(by=['Kategori', 'Tahun', 'Nama Penyanyi', 'Judul Lagu'], inplace=True, ignore_index=True)
            final_df.to_excel(xlsx_output_path, index=False)
            print(f" -> Berhasil mengompilasi Excel final bersih: {colorama.Fore.GREEN}{xlsx_output_name}{colorama.Style.RESET_ALL}")
        else:
            print(f"{colorama.Fore.YELLOW} [Peringatan] Hasil akhir kosong setelah difilter.{colorama.Style.RESET_ALL}")
    except Exception as e:
        print(f"{colorama.Fore.RED} [Error] Gagal menulis file Excel final: {e}{colorama.Style.RESET_ALL}")
        
    # 6. Beautiful Statistics Dashboard in Terminal
    print(f"\n{colorama.Fore.CYAN}=========================================================={colorama.Style.RESET_ALL}")
    print(f"                 RINGKASAN FILTER & KOREKSI               ")
    print(f"{colorama.Fore.CYAN}=========================================================={colorama.Style.RESET_ALL}")
    print(f"  Lagu Awal Masuk       : {colorama.Fore.WHITE}{stats['total_in']} lagu{colorama.Style.RESET_ALL}")
    print(f"  Dihapus (Lokal Heuristik) : {colorama.Fore.RED}-{stats['deleted_local_compilation']} lagu (Kompilasi/Medley/Mix){colorama.Style.RESET_ALL}")
    print(f"  Dihapus (Online Web Check): {colorama.Fore.RED}-{stats['deleted_online_compilation']} lagu (Kompilasi di web){colorama.Style.RESET_ALL}")
    print(f"  Dihapus (Lagu Palsu/Obscure): {colorama.Fore.RED}-{stats['deleted_not_found']} lagu (Tidak ditemukan di internet){colorama.Style.RESET_ALL}")
    print(f"  Koreksi Terbalik (Swapped): {colorama.Fore.YELLOW}+{stats['swapped_corrected']} lagu berhasil diperbaiki{colorama.Style.RESET_ALL}")
    print(f"  Koreksi Ejaan & Casing     : {colorama.Fore.YELLOW}+{stats['spelling_corrected']} lagu diselaraskan{colorama.Style.RESET_ALL}")
    print(f"  Koreksi Tahun Lagu         : {colorama.Fore.YELLOW}+{stats['year_corrected']} tahun rilis diperbarui{colorama.Style.RESET_ALL}")
    print(f"  Lagu Bersih Lolos (Final)  : {colorama.Fore.GREEN}{stats['kept_clean']} lagu{colorama.Style.RESET_ALL}")
    
    rate_deleted = ((stats['total_in'] - stats['kept_clean']) / stats['total_in']) * 100 if stats['total_in'] > 0 else 0
    print(f"  Rasio Data Sampah Dibuang  : {colorama.Fore.CYAN}{rate_deleted:.1f}%{colorama.Style.RESET_ALL}")
    print(f"{colorama.Fore.CYAN}=========================================================={colorama.Style.RESET_ALL}")
    print(f"{colorama.Fore.GREEN} Selesai! File final tersimpan di generator\\{xlsx_output_name}{colorama.Style.RESET_ALL}\n")

if __name__ == "__main__":
    main()
