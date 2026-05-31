import os
import sys
import colorama

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import filter_songs

colorama.init()

def run_filter_tests():
    print(f"{colorama.Fore.CYAN}=== MENJALANKAN PENGUJIAN BOT FILTER LAGU ==={colorama.Style.RESET_ALL}\n")

    # 1. Test local heuristics
    test_cases_local = [
        ("Tipe-X", "Kompilasi Sakit Hati", True, "kompilasi"),
        ("Tembang Kenangan", "Sakit Hati", True, "tembang kenangan"),
        ("Lesti Kejora", "Sekali Seumur Hidup (Karaoke Medley)", True, "medley"),
        ("Happy Asmara", "Rungkad (DJ Mix Nonstop)", True, "mix"),
        ("Dewa 19", "Kangen", False, None),
        ("Lyodra", "Pesan Terakhir", False, None),
    ]

    local_passed = True
    print(f"{colorama.Fore.YELLOW}[1] Menguji Filter Heuristik Lokal...{colorama.Style.RESET_ALL}")
    for art, tit, exp_comp, exp_kw in test_cases_local:
        is_comp, kw = filter_songs.is_local_compilation(art, tit)
        if is_comp == exp_comp:
            print(f"  {colorama.Fore.GREEN}PASS:{colorama.Style.RESET_ALL} '{art}' - '{tit}' -> Kompilasi: {is_comp} (Kata kunci terdeteksi: {kw})")
        else:
            print(f"  {colorama.Fore.RED}FAIL:{colorama.Style.RESET_ALL} '{art}' - '{tit}' -> Terdeteksi: {is_comp} (Kata kunci: {kw}), Diharapkan: {exp_comp}")
            local_passed = False

    # 2. Test metadata correction from search results (mocked)
    print(f"\n{colorama.Fore.YELLOW}[2] Menguji Koreksi Metadata dari Hasil Pencarian (Mocked)...{colorama.Style.RESET_ALL}")
    
    # Case A: Swapped Artist and Title
    # Input: Artist = "Usai", Title = "Tiara Andini"
    # Search result has page titles like: "Tiara Andini - Usai Lyrics | Genius Lyrics", "Tiara Andini - Usai (Official Video)"
    mock_titles_A = [
        "Tiara Andini - Usai Lyrics | Genius Lyrics",
        "Tiara Andini - Usai - YouTube",
        "Lirik Lagu Usai dari Tiara Andini"
    ]
    mock_snippets_A = [
        "Lirik Lagu Usai yang dinyanyikan oleh Tiara Andini dirilis pada tahun 2022.",
        "Tiara Andini - Usai (Official Music Video)"
    ]
    
    c_art_A, c_tit_A, c_year_A, valid_A, reason_A = filter_songs.correct_metadata_from_web(
        "Usai", "Tiara Andini", 2024, mock_titles_A, mock_snippets_A
    )
    
    if c_art_A == "Tiara Andini" and c_tit_A == "Usai" and c_year_A == 2022:
        print(f"  {colorama.Fore.GREEN}PASS:{colorama.Style.RESET_ALL} Swapped correction: 'Usai' - 'Tiara Andini' -> '{c_art_A}' - '{c_tit_A}' (Tahun: {c_year_A})")
    else:
        print(f"  {colorama.Fore.RED}FAIL:{colorama.Style.RESET_ALL} Swapped correction: 'Usai' - 'Tiara Andini' -> '{c_art_A}' - '{c_tit_A}' (Tahun: {c_year_A}), Diharapkan: 'Tiara Andini' - 'Usai' (Tahun: 2022)")
        local_passed = False

    # Case B: Casing/Spelling alignment and Special Band Names
    mock_titles_B = [
        "Tipe-X - Sakit Hati Lyrics - Genius",
        "Tipe-X - Sakit Hati - YouTube"
    ]
    mock_snippets_B = [
        "Sakit Hati by Tipe-X released in 1999."
    ]
    c_art_B, c_tit_B, c_year_B, valid_B, reason_B = filter_songs.correct_metadata_from_web(
        "tipe-x", "sakit hati", 2020, mock_titles_B, mock_snippets_B
    )
    if c_art_B == "Tipe-X" and c_tit_B == "Sakit Hati" and c_year_B == 1999:
        print(f"  {colorama.Fore.GREEN}PASS:{colorama.Style.RESET_ALL} Casing correction: 'tipe-x' - 'sakit hati' -> '{c_art_B}' - '{c_tit_B}' (Tahun: {c_year_B})")
    else:
        print(f"  {colorama.Fore.RED}FAIL:{colorama.Style.RESET_ALL} Casing correction: 'tipe-x' - 'sakit hati' -> '{c_art_B}' - '{c_tit_B}' (Tahun: {c_year_B}), Diharapkan: 'Tipe-X' - 'Sakit Hati' (Tahun: 1999)")
        local_passed = False

    print(f"\n{colorama.Fore.CYAN}==========================================={colorama.Style.RESET_ALL}")
    if local_passed:
        print(f"{colorama.Fore.GREEN}SEMUA PENGUJIAN BOT FILTER BERHASIL SELESAI!{colorama.Style.RESET_ALL}")
    else:
        print(f"{colorama.Fore.RED}BEBERAPA PENGUJIAN BOT FILTER GAGAL.{colorama.Style.RESET_ALL}")

if __name__ == "__main__":
    run_filter_tests()
