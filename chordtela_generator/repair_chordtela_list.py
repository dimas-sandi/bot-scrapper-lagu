import os
import sys
import re
import csv
import shutil
import pandas as pd
import colorama

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from generate_chordtela_list import INDEX_PAGES, fetch_html, ArtistIndexParser, clean_song_text

colorama.init()

def clean_for_match(s):
    return re.sub(r'[^a-z0-9\s]', '', s.lower()).strip()

def get_matching_artists(part_clean, known_artists_set):
    words = part_clean.split()
    n = len(words)
    matches = []
    # Check all contiguous sublists of words (up to 5-gram)
    for length in range(1, min(n + 1, 6)):
        for i in range(n - length + 1):
            gram = " ".join(words[i:i+length])
            if gram in known_artists_set:
                matches.append(gram)
    return matches

def main():
    proj_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(proj_dir, "list_lagu_chordtela.csv")
    xlsx_path = os.path.join(proj_dir, "list_lagu_chordtela.xlsx")
    csv_backup_path = os.path.join(proj_dir, "list_lagu_chordtela.csv.bak")
    
    print(f"{colorama.Fore.GREEN}=========================================================={colorama.Style.RESET_ALL}")
    print(f"         CHORDTELA LIST REPAIR & AUTO-SWAP UTILITY        ")
    print(f"{colorama.Fore.GREEN}=========================================================={colorama.Style.RESET_ALL}")
    
    if not os.path.exists(csv_path):
        print(f"{colorama.Fore.RED}[Error] Berkas CSV '{csv_path}' tidak ditemukan!{colorama.Style.RESET_ALL}")
        return

    # 1. Fetch all artist names from Chordtela indexes (A-Z, 0-9)
    print(" Menghubungkan ke Chordtela untuk mengunduh daftar artis resmi...")
    known_artists_set = set()
    artist_display_names = set()
    
    for letter_name, index_url in INDEX_PAGES:
        print(f"  Mengunduh indeks artis: {colorama.Fore.CYAN}{letter_name}{colorama.Style.RESET_ALL}...", end="", flush=True)
        html_index = fetch_html(index_url)
        if not html_index:
            print(f" {colorama.Fore.RED}[Gagal]{colorama.Style.RESET_ALL}")
            continue
            
        parser_idx = ArtistIndexParser()
        parser_idx.feed(html_index)
        
        count = 0
        for _, name in parser_idx.artist_links:
            clean_name = clean_for_match(name)
            if clean_name:
                known_artists_set.add(clean_name)
                artist_display_names.add(name)
                count += 1
        print(f" {colorama.Fore.GREEN}[Berhasil, +{count} artis]{colorama.Style.RESET_ALL}")
        
    print(f"\n Total basis data artis terdaftar: {colorama.Fore.GREEN}{len(known_artists_set)}{colorama.Style.RESET_ALL} artis.")
    
    # 2. Make backup of CSV
    print(f" Membuat salinan cadangan berkas CSV ke '{csv_backup_path}'...")
    try:
        shutil.copy2(csv_path, csv_backup_path)
        print(f" -> {colorama.Fore.GREEN}Backup berhasil.{colorama.Style.RESET_ALL}")
    except Exception as e:
        print(f" {colorama.Fore.RED}[Warning] Gagal membuat backup: {e}. Melanjutkan...{colorama.Style.RESET_ALL}")

    # 3. Read and repair CSV rows
    print(" Membaca dan memproses baris CSV...")
    repaired_rows = []
    total_rows = 0
    swapped_count = 0
    swapped_examples = []
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            
            for row in reader:
                total_rows += 1
                p1 = row.get('Nama Penyanyi', '').strip()
                p2 = row.get('Judul Lagu', '').strip()
                
                clean_p1 = clean_for_match(p1)
                clean_p2 = clean_for_match(p2)
                
                matches1 = get_matching_artists(clean_p1, known_artists_set)
                matches2 = get_matching_artists(clean_p2, known_artists_set)
                
                swap = False
                # If part2 matches a known artist but part1 does not, we swap
                if matches2 and not matches1:
                    swap = True
                # If both match, check word difference length (shorter distance to exact artist wins)
                elif matches1 and matches2:
                    # Let's see if one matches exactly
                    exact1 = any(m == clean_p1 for m in matches1)
                    exact2 = any(m == clean_p2 for m in matches2)
                    if exact2 and not exact1:
                        swap = True
                
                if swap:
                    row['Nama Penyanyi'] = p2
                    row['Judul Lagu'] = p1
                    swapped_count += 1
                    if len(swapped_examples) < 15:
                        swapped_examples.append((p1, p2, p2, p1))
                
                repaired_rows.append(row)
                
    except Exception as e:
        print(f" {colorama.Fore.RED}[Error] Gagal membaca CSV: {e}{colorama.Style.RESET_ALL}")
        return

    # 4. Save repaired rows back to CSV
    print(f" Menyimpan berkas CSV yang telah diperbaiki ke '{csv_path}'...")
    try:
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(repaired_rows)
        print(f" -> {colorama.Fore.GREEN}Penyimpanan CSV sukses.{colorama.Style.RESET_ALL}")
    except Exception as e:
        print(f" {colorama.Fore.RED}[Error] Gagal menulis ke CSV: {e}{colorama.Style.RESET_ALL}")
        return

    # 5. Convert to Excel
    print(f" Mengonversi berkas CSV ke Excel '{xlsx_path}'...")
    try:
        df = pd.read_csv(csv_path)
        df.sort_values(by=['Nama Penyanyi', 'Judul Lagu'], inplace=True, ignore_index=True)
        df.to_excel(xlsx_path, index=False)
        print(f" -> {colorama.Fore.GREEN}Penyimpanan Excel sukses.{colorama.Style.RESET_ALL}")
    except Exception as e:
        print(f" {colorama.Fore.RED}[Error] Gagal mengonversi ke Excel: {e}{colorama.Style.RESET_ALL}")

    # 6. Show summary
    print(f"\n{colorama.Fore.GREEN}==================== RINGKASAN REPARASI ===================={colorama.Style.RESET_ALL}")
    print(f" Total baris diperiksa: {colorama.Fore.CYAN}{total_rows}{colorama.Style.RESET_ALL}")
    print(f" Total baris ditukar (swapped): {colorama.Fore.YELLOW}{swapped_count}{colorama.Style.RESET_ALL}")
    print(f"============================================================")
    
    if swapped_examples:
        print(f"\n Contoh data terbalik yang berhasil diperbaiki:")
        for idx, (old_art, old_title, new_art, new_title) in enumerate(swapped_examples):
            print(f"  {idx+1}. [Terbalik] '{old_art}' - '{old_title}'")
            print(f"     [Menjadi]  '{new_art}' - '{new_title}'")
            
    print(f"\n{colorama.Fore.GREEN} Reparasi selesai dengan sukses!{colorama.Style.RESET_ALL}")

if __name__ == "__main__":
    main()
