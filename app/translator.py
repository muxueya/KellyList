from langdetect import detect
from googletrans import Translator
import re
from bs4 import BeautifulSoup
import requests

translator = Translator()
API_URL = 'https://folkets-lexikon.csc.kth.se/folkets/service'

def fetch_html(word, lang='sv', interface='en'):
    word = word.lower()
    params = {'word': word, 'lang': lang, 'interface': interface}
    response = requests.get(API_URL, params=params)
    response.raise_for_status()
    return response.text


def get_formatted_entry(word):
    """
    Fetch and return a clean HTML fragment of all <p> entries for the given word,
    replacing only the two flag PNGs with emojis and removing every other image.
    """
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
    soup = BeautifulSoup(html, 'html.parser')

    # === CHANGES: precise flag→emoji mapping, strip other images ===
    # for img in soup.find_all('img'):
    #     src = img.get('src', '')
    #     if src.endswith('flag_18x12_sv.png'):
    #         img.replace_with('🇸🇪')
    #     elif src.endswith('flag_18x12_en.png'):
    #         img.replace_with('🇬🇧')
    #     else:
    #         img.decompose()
    # # === END CHANGES ===

    # === CHANGES: grab every <p> tag’s full HTML, no text‑only extraction ===
    paragraphs = soup.find_all('p')
    if not paragraphs:
        return None

    # Join them verbatim so <b>, commas, <br>, and all text stay exactly as on the page
    entry_html = "".join(str(p) for p in paragraphs)
    # === END CHANGES ===

    return entry_html




def translate_text(text):
    """
    Detect language and translate text using Google Translate.
    """
    try:
        src = detect(text)
        dest = 'en' if src == 'sv' else 'sv'
        return translator.translate(text, src=src, dest=dest).text
    except Exception as e:
        return f"[Error] {e}"
