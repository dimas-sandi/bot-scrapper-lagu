import urllib.request
import urllib.parse
import json

def test_wiki(query, lang='id'):
    encoded = urllib.parse.quote(query)
    url = f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search&srsearch={encoded}&format=json"
    req = urllib.request.Request(url, headers={'User-Agent': 'KaraokeGenreRepair/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            search_results = data.get('query', {}).get('search', [])
            print(f"Wikipedia {lang.upper()} results for '{query}':")
            for idx, item in enumerate(search_results[:3]):
                print(f"  {idx+1}. Title: {item.get('title')}")
                print(f"     Snippet: {item.get('snippet')}")
    except Exception as e:
        print("Error:", e)

test_wiki("Abah Lala", "id")
print()
test_wiki("Exists band", "id")
print()
test_wiki("Taylor Swift", "en")
