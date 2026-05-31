import urllib.request
import urllib.parse
import re

def debug_query(artist, title):
    query = f'"{artist}" "{title}"'
    encoded_query = urllib.parse.quote_plus(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
    
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            
        print("=== DEBUG DUCKDUCKGO ===")
        print("No results checking:")
        print("No results found in HTML:", "No results found" in html)
        print("tidak ditemukan hasil in HTML:", "tidak ditemukan hasil" in html)
        
        snippets = re.findall(r'<a class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
        titles = re.findall(r'<a class="result__url"[^>]*>(.*?)</a>', html, re.DOTALL)
        
        print("\nFound Snippets:", len(snippets))
        for i, s in enumerate(snippets[:3]):
            print(f"  {i+1}: {s.strip()[:100]}")
            
        print("\nFound Titles/URLs:", len(titles))
        for i, t in enumerate(titles[:3]):
            print(f"  {i+1}: {t.strip()[:100]}")
            
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    debug_query("PenyanyiPalsuSekali", "JudulLaguYangTidakPernahAda12345")
