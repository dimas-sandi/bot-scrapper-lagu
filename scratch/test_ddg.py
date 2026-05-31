import urllib.request
import urllib.parse
import re
from html.parser import HTMLParser

class DDGParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_snippet = False
        self.snippets = []
        self.current_class = ""

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        # DuckDuckGo HTML search results snippets are usually in a <a> or <div> with class "result__snippet"
        if tag == "a" and "result__snippet" in attrs_dict.get("class", ""):
            self.in_snippet = True
        elif tag == "div" and "result__snippet" in attrs_dict.get("class", ""):
            self.in_snippet = True

    def handle_endtag(self, tag):
        if tag in ["a", "div"]:
            self.in_snippet = False

    def handle_data(self, data):
        if self.in_snippet:
            self.snippets.append(data.strip())

def search_ddg(query):
    encoded_query = urllib.parse.quote(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7'
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html_content = resp.read().decode('utf-8', errors='ignore')
            parser = DDGParser()
            parser.feed(html_content)
            return parser.snippets
    except Exception as e:
        print(f"Error querying DDG for '{query}': {e}")
        return []

# Test
print("Searching for 'Abah Lala origin'...")
snippets = search_ddg("Abah Lala asal profil")
for s in snippets[:5]:
    print(" -", s)
print()
print("Searching for 'Taylor Swift wikipedia'...")
snippets = search_ddg("Taylor Swift wikipedia")
for s in snippets[:5]:
    print(" -", s)
