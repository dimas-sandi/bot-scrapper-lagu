import os
import sys
import colorama

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import list_generator

colorama.init()

def run_tests():
    print(f"{colorama.Fore.CYAN}=== MENJALANKAN PENGUJIAN VALIDASI LAGU ==={colorama.Style.RESET_ALL}\n")
    
    # 1. Test parser title
    test_cases_parser = [
        ("Tipe-X - Sakit Hati", "Karaoke Channel", "Tipe-X", "Sakit Hati"),
        ("Blink-182 - All The Small Things", "Pop Punk", "Blink-182", "All The Small Things"),
        ("Tipe-X-Boyband", "Official Channel", "Tipe-X", "Boyband"),
        ("Lesti Kejora - Sekali Seumur Hidup", "Dangdut", "Lesti Kejora", "Sekali Seumur Hidup"),
        ("Tipe - X - Selamat Ulang Tahun", "Music", "Tipe-X", "Selamat Ulang Tahun"),
        ("Mawar Hitam - Tipe-X", "Karaoke Zone", "Tipe-X", "Mawar Hitam"), # Swapped (lookup via TOP_ARTISTS database)
        ("Pesan Terakhir - Lyodra", "Lyodra Official", "Lyodra", "Pesan Terakhir"), # Swapped (lookup via channel name)
    ]
    
    parser_passed = True
    print(f"{colorama.Fore.YELLOW}[1] Menguji Parser Judul Video...{colorama.Style.RESET_ALL}")
    for title, channel, exp_art, exp_tit in test_cases_parser:
        art, tit = list_generator.parse_video_title(title, channel)
        if art.lower() == exp_art.lower() and tit.lower() == exp_tit.lower():
            print(f"  {colorama.Fore.GREEN}PASS:{colorama.Style.RESET_ALL} '{title}' -> Penyanyi: '{art}', Judul: '{tit}'")
        else:
            print(f"  {colorama.Fore.RED}FAIL:{colorama.Style.RESET_ALL} '{title}' -> Di-parse: '{art}' - '{tit}', Diharapkan: '{exp_art}' - '{exp_tit}'")
            parser_passed = False
            
    # 2. Test local heuristics
    test_cases_heuristics = [
        ("Tipe", "X", True),
        ("X", "Sakit Hati", True),
        ("Lesti Kejora", "Sekali Seumur Hidup", False),
        ("BTS", "Dynamite", False), # BTS is in allowed list
        ("Dewa 19", "Kangen", False),
        ("Unknown", "Lagu Baru", True),
        ("Mahalini", "A", True), # title too short
    ]
    
    heuristics_passed = True
    print(f"\n{colorama.Fore.YELLOW}[2] Menguji Filter Heuristik Lokal...{colorama.Style.RESET_ALL}")
    for art, tit, exp_susp in test_cases_heuristics:
        susp = list_generator.is_suspicious_entry(art, tit)
        if susp == exp_susp:
            print(f"  {colorama.Fore.GREEN}PASS:{colorama.Style.RESET_ALL} '{art}' - '{tit}' -> Mencurigakan: {susp}")
        else:
            print(f"  {colorama.Fore.RED}FAIL:{colorama.Style.RESET_ALL} '{art}' - '{tit}' -> Terdeteksi: {susp}, Diharapkan: {exp_susp}")
            heuristics_passed = False
            
    # 3. Test online validation (selective)
    test_cases_online = [
        ("Tipe-X", "Sakit Hati", True),
        ("Lesti Kejora", "Sekali Seumur Hidup", True),
        ("Tipe", "X", False), # should fail fast
        ("PenyanyiPalsuSekali", "JudulLaguYangTidakPernahAda12345", False),
    ]
    
    online_passed = True
    print(f"\n{colorama.Fore.YELLOW}[3] Menguji Validasi Online DuckDuckGo...{colorama.Style.RESET_ALL}")
    for art, tit, exp_valid in test_cases_online:
        print(f"  Memvalidasi '{art}' - '{tit}' secara online...")
        c_art, c_tit, valid = list_generator.validate_song_online(art, tit)
        if valid == exp_valid:
            print(f"  -> {colorama.Fore.GREEN}PASS:{colorama.Style.RESET_ALL} Valid: {valid}")
        elif list_generator.LAST_SEARCH_HAD_ERROR:
            print(f"  -> {colorama.Fore.YELLOW}TOLERATED:{colorama.Style.RESET_ALL} (Toleransi karena kesalahan koneksi)")
        else:
            print(f"  -> {colorama.Fore.RED}FAIL:{colorama.Style.RESET_ALL} Hasil: {valid}, Diharapkan: {exp_valid}")
            online_passed = False
            
    print(f"\n{colorama.Fore.CYAN}==========================================={colorama.Style.RESET_ALL}")
    if parser_passed and heuristics_passed and online_passed:
        print(f"{colorama.Fore.GREEN}SEMUA PENGUJIAN BERHASIL SELESAI!{colorama.Style.RESET_ALL}")
    else:
        print(f"{colorama.Fore.RED}BEBERAPA PENGUJIAN GAGAL. SIlakan cek kode kembali.{colorama.Style.RESET_ALL}")
        
if __name__ == "__main__":
    run_tests()
