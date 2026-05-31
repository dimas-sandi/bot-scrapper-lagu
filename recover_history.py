import os
import json

def recover_history(history_path="download_history.json"):
    directories_to_scan = [
        "D:\\Karaoke_Downloads",
        "E:\\Karaoke_Downloads"
    ]
    
    history = {}
    total_found = 0
    
    for download_dir in directories_to_scan:
        if not os.path.exists(download_dir):
            print(f"Directory {download_dir} not found! Skipping...")
            continue
            
        print(f"Scanning {download_dir} for .mp4 files...")
        for root, dirs, files in os.walk(download_dir):
            for file in files:
                if file.endswith(".mp4"):
                    full_path = os.path.join(root, file)
                    basename = os.path.splitext(file)[0]
                    song_key = basename
                    
                    history[song_key] = {
                        'artist': "Unknown",
                        'title': "Unknown",
                        'status': 'Completed',
                        'file_path': full_path
                    }
                    total_found += 1
                
    with open(history_path, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=4, ensure_ascii=False)
        
    print(f"Recovery complete! Found {total_found} downloaded songs across all drives.")
    print(f"Saved recovered history to {history_path}")

if __name__ == "__main__":
    recover_history()
