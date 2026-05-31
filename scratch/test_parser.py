import re
import html

def clean_song_text(text):
    text = html.unescape(text)
    # Remove bracketed details
    text = re.sub(r'[\(\[]\s*(chord|kunci gitar|chord dasar|lirik dan chord|lirik|cover|feat)[^\]\)]*[\)\]]', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^(chord|kunci gitar|lirik)\s+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+(chord|kunci gitar|lirik)$', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def parse_song_text(text, current_artist_name=""):
    cleaned = clean_song_text(text)
    parts = re.split(r'\s+-\s+|\s+–\s+|\s+—\s+', cleaned, maxsplit=1)
    if len(parts) == 2:
        part1 = parts[0].strip()
        part2 = parts[1].strip()
        
        if current_artist_name:
            def clean_for_match(s):
                return re.sub(r'[^a-z0-9\s]', '', s.lower()).strip()
                
            clean_artist = clean_for_match(current_artist_name)
            clean_part1 = clean_for_match(part1)
            clean_part2 = clean_for_match(part2)
            
            def has_artist_words(part_clean, artist_clean):
                if not artist_clean or not part_clean:
                    return False
                words_artist = artist_clean.split()
                words_part = part_clean.split()
                if not words_artist or not words_part:
                    return False
                n_artist = len(words_artist)
                n_part = len(words_part)
                for i in range(n_part - n_artist + 1):
                    if words_part[i:i+n_artist] == words_artist:
                        return True
                return False
                
            match1 = has_artist_words(clean_part1, clean_artist)
            match2 = has_artist_words(clean_part2, clean_artist)
            
            if match1 and match2:
                exact1 = (clean_part1 == clean_artist)
                exact2 = (clean_part2 == clean_artist)
                if exact1 and not exact2:
                    swap = False
                elif exact2 and not exact1:
                    swap = True
                else:
                    len_art = len(clean_artist.split())
                    diff1 = abs(len(clean_part1.split()) - len_art)
                    diff2 = abs(len(clean_part2.split()) - len_art)
                    swap = (diff2 < diff1)
            elif match2 and not match1:
                swap = True
            else:
                swap = False
                
            if swap:
                artist = part2
                title = part1
            else:
                artist = part1
                title = part2
        else:
            artist = part1
            title = part2
    else:
        artist = "Unknown"
        title = cleaned
        
    return artist, title

# Test cases
test_cases = [
    # (input_text, current_artist_name, expected_artist, expected_title)
    ("Abah Lala - Tatas", "Abah Lala", "Abah Lala", "Tatas"),
    ("Tatas - Abah Lala", "Abah Lala", "Abah Lala", "Tatas"),
    ("Abah Lala feat. Ndarboy Genk - Tatas", "Abah Lala", "Abah Lala feat. Ndarboy Genk", "Tatas"),
    ("Tatas - Abah Lala feat. Ndarboy Genk", "Abah Lala", "Abah Lala feat. Ndarboy Genk", "Tatas"),
    ("Noah - Separuh Aku", "Noah", "Noah", "Separuh Aku"),
    ("Separuh Aku - Noah", "Noah", "Noah", "Separuh Aku"),
    ("Separuh Aku - Noah feat. Momo", "Noah", "Noah feat. Momo", "Separuh Aku"),
    ("Guyon Waton - Perlahan", "Guyon Waton", "Guyon Waton", "Perlahan"),
    ("Perlahan - Guyon Waton", "Guyon Waton", "Guyon Waton", "Perlahan"),
    ("Sanes - Guyon Waton x Denny Caknan", "Guyon Waton", "Guyon Waton x Denny Caknan", "Sanes"),
    ("Guyon Waton x Denny Caknan - Sanes", "Guyon Waton", "Guyon Waton x Denny Caknan", "Sanes"),
    ("Chord Lagu Keren", "Noah", "Unknown", "Lagu Keren"),
]

passed_all = True
for idx, (inp, art_name, exp_art, exp_title) in enumerate(test_cases):
    res_art, res_title = parse_song_text(inp, art_name)
    if res_art == exp_art and res_title == exp_title:
        print(f"Test case {idx+1}: PASS ('{inp}' with artist '{art_name}' -> '{res_art}' - '{res_title}')")
    else:
        print(f"Test case {idx+1}: FAIL! ('{inp}' with artist '{art_name}')")
        print(f"  Expected: '{exp_art}' - '{exp_title}'")
        print(f"  Got:      '{res_art}' - '{res_title}'")
        passed_all = False

if passed_all:
    print("\nALL TEST CASES PASSED SUCCESSFULLY!")
else:
    print("\nSOME TEST CASES FAILED!")
