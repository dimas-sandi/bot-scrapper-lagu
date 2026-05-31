import os
import sys

# Add src to path
proj_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(proj_dir, "src"))

import excel_handler

def test():
    excel_path = r"D:\list lagu.xls"
    print("Reading songs using excel_handler...")
    songs = excel_handler.read_song_list(excel_path)
    print(f"Total songs parsed by excel_handler: {len(songs)}")
    
    unique_keys = set(f"{s['artist']} - {s['title']}" for s in songs)
    print(f"Total unique song keys (artist - title): {len(unique_keys)}")

if __name__ == "__main__":
    test()
