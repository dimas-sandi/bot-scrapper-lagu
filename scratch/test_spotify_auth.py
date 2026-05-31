import urllib.request
import urllib.parse
import json
import base64

client_id = "c5be9a38d0c54e87b31a3e7c84003577"
client_secret = "7e71c054d1804ca2ad4cdcc4e4ee3ea9"

auth_str = f"{client_id}:{client_secret}"
auth_b64 = base64.b64encode(auth_str.encode()).decode()
url = "https://accounts.spotify.com/api/token"
req = urllib.request.Request(url, headers={
    'Authorization': f'Basic {auth_b64}',
    'Content-Type': 'application/x-www-form-urlencoded'
}, data=b'grant_type=client_credentials')

try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())
        token = data.get('access_token')
        print("Access token obtained:", token[:20] + "...")
        
        # Test query for artist "Abah Lala"
        query = urllib.parse.quote("Abah Lala")
        search_url = f"https://api.spotify.com/v1/search?q={query}&type=artist&limit=1"
        search_req = urllib.request.Request(search_url, headers={
            'Authorization': f'Bearer {token}'
        })
        with urllib.request.urlopen(search_req, timeout=10) as s_resp:
            s_data = json.loads(s_resp.read().decode())
            artists = s_data.get('artists', {}).get('items', [])
            if artists:
                artist = artists[0]
                print("Artist Name:", artist.get('name'))
                print("Genres:", artist.get('genres'))
            else:
                print("Artist not found.")
except Exception as e:
    print("Error:", e)
