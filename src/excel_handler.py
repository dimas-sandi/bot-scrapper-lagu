import os
import pandas as pd
import re

def clean_filename(name):
    """Sanitize string to be used as a safe filename."""
    if not name:
        return "Unknown"
    # Remove characters that are illegal in Windows filenames
    name = re.sub(r'[\\/*?:"<>|]', '', str(name))
    # Replace multiple spaces with a single space and strip
    return re.sub(r'\s+', ' ', name).strip()

def clean_category(name):
    """Sanitize category/genre name to be safe for directory names."""
    clean = clean_filename(name)
    if not clean or clean.lower() == 'nan':
        return "Lainnya"
    # Convert to Title Case
    return clean.title()

def clean_text_proper(text):
    """Clean and capitalize names properly (Title Case)."""
    if pd.isna(text) or not str(text).strip():
        return ""
    text = str(text).strip()
    # Replace multiple spaces
    text = re.sub(r'\s+', ' ', text)
    return text.title()

def detect_columns(df):
    """Detect artist, title, and category/genre columns from a DataFrame."""
    singer_cols = ['penyanyi', 'nama penyanyi', 'singer', 'artist', 'nama', 'artis']
    title_cols = ['judul', 'judul lagu', 'judul_lagu', 'jdl_lagu', 'jdl lagu', 'title', 'lagu', 'song']
    category_cols = ['kategori', 'katagori', 'genre', 'category', 'group', 'tipe', 'type', 'kelas']
    
    detected = {'artist': None, 'title': None, 'category': None}
    
    # Check by name matching
    for col in df.columns:
        col_str = str(col).lower().strip()
        if col_str in singer_cols:
            detected['artist'] = col
        elif col_str in title_cols:
            detected['title'] = col
        elif col_str in category_cols:
            detected['category'] = col
            
    # Fallback to column index if names not detected
    cols = list(df.columns)
    if not detected['artist'] and len(cols) > 0:
        detected['artist'] = cols[0]
    if not detected['title'] and len(cols) > 1:
        detected['title'] = cols[1]
    if not detected['category'] and len(cols) > 2:
        detected['category'] = cols[2]
        
    return detected

def read_song_list(file_path):
    """
    Reads song list from Excel (.xls, .xlsx) or CSV.
    Returns a list of dicts with cleaned 'artist', 'title', 'category' keys.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File Excel tidak ditemukan di: {file_path}")
        
    # Read file based on extension
    _, ext = os.path.splitext(file_path.lower())
    if ext == '.csv':
        df = pd.read_csv(file_path)
    elif ext in ['.xls', '.xlsx']:
        # pandas automatically uses openpyxl for xlsx and xlrd for xls
        df = pd.read_excel(file_path)
    else:
        raise ValueError("Format file tidak didukung! Gunakan .xls, .xlsx, atau .csv")
        
    # Standardize and detect columns
    detected = detect_columns(df)
    
    songs = []
    for idx, row in df.iterrows():
        # Retrieve values using detected keys, fallback to empty string
        artist_val = row[detected['artist']] if detected['artist'] else ""
        title_val = row[detected['title']] if detected['title'] else ""
        category_val = row[detected['category']] if detected['category'] else "Lainnya"
        
        # Proper cleaning
        artist = clean_text_proper(artist_val)
        title = clean_text_proper(title_val)
        category = clean_category(category_val)
        
        # Skip rows that are completely empty
        if not artist and not title:
            continue
            
        songs.append({
            'index': idx + 1,
            'artist': artist or "Penyanyi Tidak Dikenal",
            'title': title or "Judul Tidak Dikenal",
            'category': category,
            'original_artist': str(artist_val).strip(),
            'original_title': str(title_val).strip(),
            'original_category': str(category_val).strip()
        })
        
    return songs

def write_clean_playlist(results, output_path):
    """
    Writes a formatted, clean Excel list of downloaded songs.
     results is a list of dictionaries with song details and download status.
    """
    df = pd.DataFrame(results)
    
    # Select and rename columns for display
    display_cols = {
        'category': 'Kategori/Genre',
        'artist': 'Nama Penyanyi',
        'title': 'Judul Lagu',
        'status': 'Status Download',
        'file_path': 'Lokasi File',
        'file_size_mb': 'Ukuran File (MB)',
        'duration_str': 'Durasi',
        'error_msg': 'Keterangan/Error'
    }
    
    # Filter to only existing columns in results
    df_write = df[[c for c in display_cols.keys() if c in df.columns]].copy()
    df_write.rename(columns=display_cols, inplace=True)
    
    # Sort nicely by Genre, Artist, and Title
    df_write.sort_values(by=['Kategori/Genre', 'Nama Penyanyi', 'Judul Lagu'], inplace=True, ignore_index=True)
    
    # Save to Excel
    directory = os.path.dirname(output_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
        
    df_write.to_excel(output_path, index=False)
    return len(df_write)
