"""Tiny keyword search over the markdown knowledge base (no external services needed)."""
import re
from functools import lru_cache
from pathlib import Path

KB_FILE = Path(__file__).with_name("homigo_kb.md")
_WORD = re.compile(r"[a-z0-9]+|[ऀ-ॿ]+")
_STOP = {
    "the", "a", "an", "is", "are", "to", "of", "and", "or", "in", "on", "for", "my", "me", "i", "you", "your", "can", "do", "how",
    "what", "it", "be", "with", "this", "that", "at", "kya", "hai", "h", "ka", "ki", "ke", "ko", "se", "mein", "me", "please",
}


@lru_cache(maxsize=1)
def sections():
    text = KB_FILE.read_text(encoding="utf-8")
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    out = []
    for block in re.split(r"^## ", text, flags=re.M)[1:]:
        lines = block.strip().splitlines()
        title = lines[0].strip()
        keywords, audience, body = [], "all", []
        for ln in lines[1:]:
            if ln.lower().startswith("keywords:"):
                keywords = [k.strip().lower() for k in ln.split(":", 1)[1].split(",") if k.strip()]
            elif ln.lower().startswith("audience:"):
                audience = ln.split(":", 1)[1].strip().lower()
            elif ln.strip():
                body.append(ln.strip())
        out.append({"title": title, "keywords": keywords, "audience": audience, "body": "\n".join(body)})
    return out


def _tokens(s):
    return [w for w in _WORD.findall(s.lower()) if w not in _STOP and len(w) > 1]


def search(query, role="guest", limit=3):
    """Returns [(score, section)] best first. Phrase hits on keywords weigh most."""
    ql = query.lower()
    qt = set(_tokens(query))
    scored = []
    for s in sections():
        if s["audience"] == "admin" and role != "admin":
            continue
        score = 0.0
        for kw in s["keywords"]:
            if " " in kw and kw in ql:
                score += 3
            elif kw in qt or (len(kw) >= 5 and any(len(w) >= 4 and (kw.startswith(w) or w.startswith(kw)) for w in qt)):
                score += 2
        title_t = set(_tokens(s["title"]))
        score += 1.5 * len({w for w in qt if any(w == tw or (len(w) >= 4 and len(tw) >= 4 and (tw.startswith(w) or w.startswith(tw))) for tw in title_t)})
        score += 0.3 * len(qt & set(_tokens(s["body"])))
        if score > 0:
            scored.append((score, s))
    scored.sort(key=lambda x: -x[0])
    return scored[:limit]


def overview(role="guest"):
    """Compact KB for the LLM system prompt."""
    parts = []
    for s in sections():
        if s["audience"] != "admin" or role == "admin":
            parts.append(f"### {s['title']}\n{s['body']}")
    return "\n\n".join(parts)
