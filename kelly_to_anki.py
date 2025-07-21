#!/usr/bin/env python3
"""
kelly_to_anki.py

Read Swedish words and their CEFR levels from the provided Excel (Kelly list),
query Folkets lexikon (fallback to Google Translate),
download or generate audio,
and produce a tab-delimited import file for Anki with [sound:] tags and CEFR tags.
"""
import os
import re
import sys
import asyncio
import requests
import pandas as pd
from bs4 import BeautifulSoup
from app.translator import translate_text, fetch_html  # reuse existing project functions
import edge_tts

# === CHANGES: include CEFR column name ===
EXCEL_FILE = 'Swedish-Kelly_M3_CEFR.csv'
SWEDISH_COLUMN = 'Swedish items for translation'
CEFR_COLUMN   = 'CEFR levels'
OUTPUT_FILE = 'kelly_anki_import.txt'
AUDIO_DIR   = 'media'   # folder to place downloaded/generated mp3s
DECK_NAME   = 'KellyList'
NOTE_TYPE   = 'Basic'

# ensure audio directory exists
os.makedirs(AUDIO_DIR, exist_ok=True)

async def tts_save(text: str, path: str):
    """Generate audio via Edge-TTS and save to path."""
    communicate = edge_tts.Communicate(text, 'sv-SE-MattiasNeural')
    await communicate.save(path)

def get_folkets_entry(word: str):
    """
    Fetch HTML for a word from Folkets lexikon service. Return HTML fragment or None.
    """
    try:
        html = fetch_html(word)
        html = re.sub(
            r'<img\s+src="grafik/flag_18x12_sv\.png"[^>]*>',
            '🇸🇪',
            html
        )
        html = re.sub(
            r'<img\s+src="grafik/flag_18x12_en\.png"[^>]*>',
            '🇬🇧',
            html
        )
        html = re.sub(
            r'<img\s+src="grafik/sound\.gif"[^>]*>',
            '🔊',
            html
        )
    except Exception:
        return None
    soup = BeautifulSoup(html, 'html.parser')
    paras = soup.find_all('p')
    if not paras:
        return None
    return ''.join(str(p) for p in paras)

def extract_mp3_url(html: str):
    """
    Return the first mp3 URL found in the HTML fragment, or None.
    """
    m = re.search(r'href=[\'"](https?://[^\'"]+\.mp3)[\'"]', html)
    return m.group(1) if m else None

def process_word(word: str):
    """
    For a single word:
      - Try Folkets lexikon (HTML + audio).
      - If no HTML, fallback to Google Translate (plain text).
      - Ensure an MP3 file exists (download or TTS).
      - Return (definition_html_or_text, sound_filename)
    """
    # === CHANGES START: split off any parenthetical for querying ===
    display_text = word.strip()                        # e.g. 'ikväll (el. i kväll)'
    query_text   = display_text.split('(')[0].strip()  # e.g. 'ikväll'
    # === END CHANGES ===

    # If after stripping it’s empty, skip
    if not display_text:
        return None, None

    # 1) Try Folkets lexikon with the truncated query_text
    entry_html = get_folkets_entry(query_text.lower())
    sound_filename = None

    # 2) Fallback to Google if Folkets had no hit
    if not entry_html:
        try:
            translated = translate_text(query_text)  # SV→EN on the base word
            if not translated or not isinstance(translated, str):
                return None, None
            entry_html = translated
        except Exception:
            return None, None

    # 3) At this point entry_html is either Folkets HTML or plain Google text

    # Existing logic: extract / download MP3, or generate via TTS
    mp3_url = extract_mp3_url(entry_html)
    if mp3_url:
        name = os.path.basename(mp3_url)
        local = os.path.join(AUDIO_DIR, name)
        if not os.path.exists(local):
            try:
                resp = requests.get(mp3_url, timeout=10)
                resp.raise_for_status()
                with open(local, 'wb') as f:
                    f.write(resp.content)
            except Exception:
                mp3_url = None
        if mp3_url:
            sound_filename = name
            pattern = fr'<a[^>]+href=["\']{re.escape(mp3_url)}["\'][^>]*>.*?</a>'
            entry_html = re.sub(
                pattern,
                f'[sound:{name}]',
                entry_html,
                flags=re.DOTALL
            )

    # 4) If we still have no Folkets audio, generate via Edge‑TTS
    if not sound_filename:
        safe_name = re.sub(r'[^A-Za-z0-9_-]', '_', query_text)
        name = f"{safe_name}.mp3"
        local = os.path.join(AUDIO_DIR, name)
        if not os.path.exists(local):
            asyncio.run(tts_save(query_text, local))
        sound_filename = name

    return entry_html, sound_filename

def main():
    # === CHANGES: read both Swedish word and its CEFR level ===
    df = pd.read_csv(
        EXCEL_FILE,
        usecols=[SWEDISH_COLUMN, CEFR_COLUMN]
    )
    # Drop rows missing words
    df = df.dropna(subset=[SWEDISH_COLUMN])
    # Convert CEFR to string, fill missing with empty
    df[CEFR_COLUMN] = df[CEFR_COLUMN].fillna('').astype(str)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as out:
        # === CHANGES: add Tags column to header ===
        out.write("#separator:Tab\n")
        out.write(f"#columns:Word\tDefinition\tTags\n")
        out.write(f"#notetype:{NOTE_TYPE}\n")
        out.write(f"#deck:{DECK_NAME}\n")
        # === END CHANGES ===

        for _, row in df.iterrows():
            word = str(row[SWEDISH_COLUMN]).strip()
            tag  = row[CEFR_COLUMN].strip()
            definition, sound = process_word(word)
            if not definition:
                continue

            # single-line definition
            def_line = definition.replace('\n', '<br>')

            # ensure sound tag appears if not already embedded
            if sound and '[sound:' not in def_line:
                def_line += f' [sound:{sound}]'

            # === CHANGES: append CEFR tag in the third column ===
            tags_field = tag or ''
            out.write(f"{word}\t{def_line}\t{tags_field}\n")
            # === END CHANGES ===

            print(f"Processed: {word} ({tags_field})")

    print(f"\nDone. Import '{OUTPUT_FILE}' (and the '{AUDIO_DIR}' folder) into Anki with 'Include media'.")
    
if __name__ == '__main__':
    main()
