import re

def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())

def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"\s+", "-", text).strip("-")

def text_stats(text: str) -> dict:
    words = text.split()
    sentences = len([s for s in re.split(r"[.!?]+", text) if s.strip()])
    return {
        "length": len(text),
        "words": len(words),
        "characters_without_spaces": len(text.replace(" ", "")),
        "sentences": sentences,
        "reading_time_minutes": round(len(words) / 200, 2),
    }
