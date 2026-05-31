import sys
import os

# Add src/ to path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

import downloader

def main():
    print("==================================================")
    print("   UJI MANDIRI SKORING POPULARITAS YOUTUBE (TUI)   ")
    print("==================================================")
    
    artist = "Noah"
    title = "Separuh Aku"
    
    print(f"Mencari karaoke untuk: {artist} - {title}...\n")
    
    try:
        # We temporarily patch or call search_youtube_karaoke
        candidates = downloader.search_youtube_karaoke(artist, title)
        
        print(f"Ditemukan {len(candidates)} kandidat valid (skor > 0):")
        for i, c in enumerate(candidates):
            print(f"\n{i+1}. Judul: {c['title']}")
            print(f"   URL  : {c['url']}")
            print(f"   Dur  : {c['duration']} detik")
            print(f"   Skor : {c['score']}")
            
            # Since Candidates returned from search_youtube_karaoke are final sorted ones, 
            # let's run a manual check on views/uploader to print details
            try:
                import yt_dlp
                ydl_opts = {
                    'noplaylist': True,
                    'quiet': True,
                    'extract_flat': False,
                    'skip_download': True,
                    'no_warnings': True,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(c['url'], download=False)
                    if info:
                        views = info.get('view_count', 0)
                        channel = info.get('channel', 'N/A')
                        verified = info.get('channel_is_verified', False)
                        print(f"   [Detail API YouTube]")
                        print(f"   * Views        : {views:,}")
                        print(f"   * Channel      : {channel}")
                        print(f"   * Verified     : {verified}")
            except Exception as e:
                print(f"   * Gagal mengambil info API detail: {e}")
                
        print("\n==================================================")
        print("          HASIL PENCARIAN TERBAIK (TOP 1)         ")
        print("==================================================")
        best = candidates[0]
        print(f"Judul Terbaik : {best['title']}")
        print(f"Skor Akhir    : {best['score']}")
        print(f"URL           : {best['url']}")
        print("==================================================")
        
    except Exception as e:
        print(f"Error terjadi: {e}")

if __name__ == "__main__":
    main()
