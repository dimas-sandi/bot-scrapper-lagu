import urllib.request
import urllib.parse
import json

def test_itunes(artist_name):
    query = urllib.parse.quote(artist_name)
    url = f"https://itunes.apple.com/search?term={query}&limit=3&entity=musicTrack"
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            results = data.get('results', [])
            print(f"Results for '{artist_name}':")
            for idx, track in enumerate(results):
                print(f"  {idx+1}. Artist: {track.get('artistName')}")
                print(f"     Track:  {track.get('trackName')}")
                print(f"     Genre:  {track.get('primaryGenreName')}")
                print(f"     Country: {track.get('country')}")
    except Exception as e:
        print("Error:", e)

test_itunes("Abah Lala")
print()
test_itunes("Taylor Swift")
print()
test_itunes("Noah")
