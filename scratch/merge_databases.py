import os
import pandas as pd
import colorama

colorama.init()

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    playlist_clean_path = os.path.join(base_dir, "Karaoke_Playlist_Clean.xlsx")
    chordtela_path = os.path.join(base_dir, "chordtela_generator", "list_lagu_chordtela.xlsx")
    merged_path = os.path.join(base_dir, "Database_Karaoke_Dimpi_2026.xlsx")
    
    print(f"{colorama.Fore.GREEN}=========================================================={colorama.Style.RESET_ALL}")
    print(f"       GABUNGKAN BASIS DATA PLAYLIST & CHORDTELA 2026     ")
    print(f"{colorama.Fore.GREEN}=========================================================={colorama.Style.RESET_ALL}")
    
    # Check if files exist
    if not os.path.exists(playlist_clean_path):
        print(f"{colorama.Fore.RED}[Error] File '{playlist_clean_path}' tidak ditemukan!{colorama.Style.RESET_ALL}")
        return
    if not os.path.exists(chordtela_path):
        print(f"{colorama.Fore.RED}[Error] File '{chordtela_path}' tidak ditemukan!{colorama.Style.RESET_ALL}")
        return
        
    # 1. Load files
    print(" Memuat berkas Karaoke_Playlist_Clean.xlsx...")
    df_clean = pd.read_excel(playlist_clean_path)
    print(f" -> Terbaca {colorama.Fore.CYAN}{len(df_clean)}{colorama.Style.RESET_ALL} baris.")
    
    print(" Memuat berkas list_lagu_chordtela.xlsx...")
    df_chord = pd.read_excel(chordtela_path)
    print(f" -> Terbaca {colorama.Fore.CYAN}{len(df_chord)}{colorama.Style.RESET_ALL} baris.")
    
    # 2. Add columns alignment
    # Ensure all columns from both dataframes are combined
    # df_clean columns: ['Kategori/Genre', 'Nama Penyanyi', 'Judul Lagu', 'Status Download', 'Lokasi File', 'Ukuran File (MB)', 'Durasi', 'Keterangan/Error']
    # df_chord columns: ['Nama Penyanyi', 'Judul Lagu', 'Kategori/Genre', 'Tautan']
    
    # We want to stack them. Concat aligns columns by name automatically
    print(" Menggabungkan kedua basis data...")
    df_merged = pd.concat([df_clean, df_chord], ignore_index=True)
    total_before_dedup = len(df_merged)
    print(f" -> Total gabungan sebelum dedup: {colorama.Fore.CYAN}{total_before_dedup}{colorama.Style.RESET_ALL} baris.")
    
    # 3. Smart Deduplication
    # Let's create a temporary key in lowercase for safe matching
    print(" Menghilangkan lagu duplikat (sensitivitas huruf besar/kecil & spasi)...")
    
    # Create normalized temp columns
    df_merged['_temp_singer'] = df_merged['Nama Penyanyi'].astype(str).str.lower().str.strip()
    df_merged['_temp_title'] = df_merged['Judul Lagu'].astype(str).str.lower().str.strip()
    
    # Drop duplicates keeping the first occurrence (df_clean is first, so downloaded files are preserved!)
    df_merged.drop_duplicates(subset=['_temp_singer', '_temp_title'], keep='first', inplace=True)
    
    # Remove temporary columns
    df_merged.drop(columns=['_temp_singer', '_temp_title'], inplace=True)
    
    total_after_dedup = len(df_merged)
    duplicates_removed = total_before_dedup - total_after_dedup
    print(f" -> Lagu duplikat yang dihapus: {colorama.Fore.YELLOW}{duplicates_removed}{colorama.Style.RESET_ALL} baris.")
    print(f" -> Total baris unik setelah dedup: {colorama.Fore.GREEN}{total_after_dedup}{colorama.Style.RESET_ALL} baris.")
    
    # 4. Sort data
    print(" Mengurutkan data berdasarkan Kategori/Genre, Nama Penyanyi, dan Judul Lagu...")
    df_merged.sort_values(by=['Kategori/Genre', 'Nama Penyanyi', 'Judul Lagu'], inplace=True, ignore_index=True)
    
    # Re-order columns to make it clean and neat
    columns_order = [
        'Kategori/Genre', 
        'Nama Penyanyi', 
        'Judul Lagu', 
        'Status Download', 
        'Lokasi File', 
        'Ukuran File (MB)', 
        'Durasi', 
        'Tautan', 
        'Keterangan/Error'
    ]
    # Keep only columns that exist (in case column names differed slightly)
    columns_to_keep = [col for col in columns_order if col in df_merged.columns]
    # Append any columns that we missed
    for col in df_merged.columns:
        if col not in columns_to_keep:
            columns_to_keep.append(col)
            
    df_merged = df_merged[columns_to_keep]
    
    # 5. Write to new Excel file
    print(f" Menyimpan berkas Excel baru ke '{merged_path}'...")
    try:
        df_merged.to_excel(merged_path, index=False)
        print(f" -> {colorama.Fore.GREEN}Sukses menyimpan Database_Karaoke_Dimpi_2026.xlsx!{colorama.Style.RESET_ALL}")
    except Exception as e:
        print(f" {colorama.Fore.RED}[Error] Gagal menyimpan Excel: {e}{colorama.Style.RESET_ALL}")
        return
        
    print(f"\n{colorama.Fore.GREEN}================== RINGKASAN GABUNGAN =================={colorama.Style.RESET_ALL}")
    print(f" Karaoke_Playlist_Clean.xlsx : {colorama.Fore.CYAN}{len(df_clean)}{colorama.Style.RESET_ALL} baris")
    print(f" list_lagu_chordtela.xlsx    : {colorama.Fore.CYAN}{len(df_chord)}{colorama.Style.RESET_ALL} baris")
    print(f" Duplikasi Dieliminasi       : {colorama.Fore.YELLOW}{duplicates_removed}{colorama.Style.RESET_ALL} baris")
    print(f" Total Baris Akhir (Unik)    : {colorama.Fore.GREEN}{len(df_merged)}{colorama.Style.RESET_ALL} baris")
    print(f" Berkas Baru Terbuat         : {colorama.Fore.CYAN}Database_Karaoke_Dimpi_2026.xlsx{colorama.Style.RESET_ALL}")
    print(f"========================================================\n")

if __name__ == "__main__":
    main()
