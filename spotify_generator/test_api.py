"""Test script to verify the new unified menu structures and limit computation logic"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_spotify_list import IDEAL_DISTRIBUTION, determine_genre

print("=" * 60)
print("  TEST: NEW UNIFIED COUNTRY STRUCTURES & LIMITS (NO PERCENTAGES)")
print("=" * 60)

# Verify IDEAL_DISTRIBUTION properties
print(f"Total Master Countries: {len(IDEAL_DISTRIBUTION)}")
for item in IDEAL_DISTRIBUTION:
    country_name, display_name, queries = item
    print(f" - {country_name:<20} | Kueri: {str(queries):<50}")

print("-" * 60)
print("[OK] Loaded categories successfully without percentages!")

# Test limit calculation for 1000 songs over 1 year (dynamic split)
total_target_songs = 1000
num_years = 1
year_limit = max(total_target_songs // num_years, 1)

print(f"\nLimit kalkulasi dinamis untuk target total {total_target_songs} lagu untuk {num_years} tahun (total tahun ini: {year_limit}):")

collected_so_far = 0
num_categories = len(IDEAL_DISTRIBUTION)
for idx, item in enumerate(IDEAL_DISTRIBUTION):
    country_name, display_name, queries = item
    remaining_categories = num_categories - idx
    remaining_target = year_limit - collected_so_far
    cat_limit = max(remaining_target // remaining_categories, 1)
    collected_so_far += cat_limit
    print(f" - {country_name:<20}: {cat_limit} lagu per tahun")

print(f" Total teralokasikan: {collected_so_far} lagu (Target: {year_limit})")
assert collected_so_far == year_limit, "Error: Dynamic allocation sum does not match target!"
print("[OK] Alokasi dinamis tepat sama dengan target tahunan!")

# Test genre determination
print("\nTesting Genre Determination:")
test_cases = [
    ("Mahalini", "Indonesia", "Sial"),
    ("Denny Caknan", "Indonesia", "Cundamani"),
    ("Hindia", "Indonesia", "Evaluasi"),
    ("Dewa 19", "Indonesia", "Kangen"),
    ("Taylor Swift", "Amerika", "Style"),
    ("Linkin Park", "Amerika", "Numb"),
    ("BTS", "Korea", "Dynamite"),
    ("Tipe-X", "Indonesia", "Genit"),
]

for art, country, title in test_cases:
    genre = determine_genre(art, country, title)
    print(f" - {art:<25} ({country}) -> Title: '{title:<20}' -> Genre: {genre}")

print("\n[OK] Semua pengujian struktur master kategori sukses!")
