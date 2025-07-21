#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import asyncio                             # === CHANGED ===
import requests
from bs4 import BeautifulSoup
import edge_tts                            # === CHANGED ===

SWEDISH_URL   = "https://www.riksdagen.se/sv/ordbok/"
ENGLISH_URL   = "https://www.riksdagen.se/en/glossary/"
OUTPUT_FILE   = "riksdagen_glossary_anki.txt"
DECK_NAME     = "LawGlossary"
NOTE_TYPE     = "Basic"
MEDIA_DIR     = "media"                   # === CHANGED: folder for downloaded audio ===

# === CHANGED: ensure media folder exists ===
os.makedirs(MEDIA_DIR, exist_ok=True)
# === END CHANGED ===

async def tts_save(text: str, path: str):
    """
    Generate Swedish TTS via Edge‑TTS and save to the given path.
    """
    communicate = edge_tts.Communicate(text, 'sv-SE-MattiasNeural')
    await communicate.save(path)

def scrape_swedish_terms_and_defs():
    """
    Return a list of (term, swedish_definition) by:
      - finding every <h3> (which holds the term)
      - taking the very next <p> as the Swedish definition
    """
    resp = requests.get(SWEDISH_URL, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    entries = []
    for h3 in soup.find_all("h3"):
        term = h3.get_text().strip()
        # grab the Swedish definition from the next <p>
        p = h3.find_next_sibling("p")
        if not p:
            continue
        sw_def = p.get_text().strip()
        entries.append((term, sw_def))
    return entries

def scrape_english_mapping():
    """
    Return a dict mapping Swedish→English using the English page’s “(Sw: X)” in each <h3>.
    """
    resp = requests.get(ENGLISH_URL, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    mapping = {}
    for h3 in soup.find_all("h3"):
        text = h3.get_text().strip()
        if "(Sw:" in text:
            # === CHANGES START: split out English term and Swedish key ===
            eng_term = text.split("(Sw:")[0].strip()            # e.g. "Adjourn"
            sw_key   = text.split("(Sw:")[1].rstrip(")").strip() # e.g. "ajournera"
            # grab the English definition from the next <p>
            p = h3.find_next_sibling("p")
            eng_def = p.get_text().strip() if p else ""
            # store under lowercase Swedish
            mapping[sw_key.lower()] = (eng_term, eng_def)
            # === END CHANGES ===
    return mapping

def sanitize_filename(text: str) -> str:
    """
    Turn arbitrary text into a safe filename.
    """
    return ''.join(c if c.isalnum() or c in '-_' else '_' for c in text)

def main():
    sw_entries = scrape_swedish_terms_and_defs()
    eng_map    = scrape_english_mapping()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        # Anki import headers
        f.write("#separator:Tab\n")
        f.write("#columns:Swedish\tDefinition\n")
        f.write(f"#notetype:{NOTE_TYPE}\n")
        f.write(f"#deck:{DECK_NAME}\n\n")

        for term, sw_def in sw_entries:
            eng = eng_map.get(term.lower(), "")

            # === CHANGED: generate or reuse a TTS MP3 for the term ===
            filename = sanitize_filename(term) + ".mp3"
            local_mp3 = os.path.join(MEDIA_DIR, filename)
            if not os.path.exists(local_mp3):
                # run Edge‑TTS synchronously
                asyncio.run(tts_save(term, local_mp3))
            # === END CHANGED ===

            # === CHANGES START: unpack English term + definition ===
            eng_entry = eng_map.get(term.lower(), ("", ""))
            eng_term, eng_def = eng_entry

            # If we got an English term, render it bold + larger, then its definition
            if eng_term:
                eng_html  = f'<div style="font-size:1.2em; font-weight:bold;">{eng_term}</div>'
                eng_html += f'<div>{eng_def}</div>'
            else:
                eng_html = ""

            # combine Swedish def + English term+def on the back
            back = f"{sw_def}<br><br>{eng_html}"
            # === END CHANGES ===

            front = f"{term} [sound:{filename}]"
            f.write(f"{front}\t{back}\n")
            print(f"Processed: {term} ({eng_term})")


    print(f"[✓] Wrote {len(sw_entries)} entries to {OUTPUT_FILE}")
    print(f"    Audio files saved in ./{MEDIA_DIR}/. Import with 'Include media'.")

if __name__ == "__main__":
    main()
