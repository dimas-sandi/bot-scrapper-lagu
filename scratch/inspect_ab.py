import os
import pandas as pd

excel_path = r"C:\Users\DIMPI\.gemini\antigravity-ide\scratch\youtube_karaoke_downloader\Karaoke_Playlist_Clean.xlsx"
print("Excel path exists:", os.path.exists(excel_path))

if os.path.exists(excel_path):
    try:
        df = pd.read_excel(excel_path)
        print("Excel columns:", list(df.columns))
        print("First 5 rows:")
        print(df.head())
        print("Total rows:", len(df))
    except Exception as e:
        print("Error reading Excel:", e)
