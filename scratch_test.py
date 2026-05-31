import sys
import os

# Add src to python path
proj_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(proj_dir, "src"))

import downloader

def test_search():
    artist = "Queen"
    title = "Bohemian Rhapsody"
    print(f"Searching for: {artist} - {title} using updated popularity scoring...")
    try:
        candidates = downloader.search_youtube_karaoke(artist, title)
        print(f"\nFound {len(candidates)} valid candidates (sorted by score descending):")
        for i, c in enumerate(candidates[:5]):
            print(f"\n[{i+1}] Title: {c['title']}")
            print(f"    URL  : {c['url']}")
            print(f"    Score: {c['score']}")
            print(f"    Dur  : {c['duration']} seconds")
    except Exception as e:
        print("Error during search:", e)

if __name__ == "__main__":
    test_search()
