"""Module for cleaning, sanitizing, and humanizing spoken Vietnamese text for dubbing & TTS.

Eliminates:
- Slashed pronouns ('anh/chị', 'ông/bà', 'bạn/quý vị') that TTS mispronounces as 'anh xuyệt chị'.
- Literal English translations of Chinese channel names (e.g. 'Star River' from 星河).
- Tech jargon and literal Douyin/Bilibili calls to action (e.g. 'long-press', 'like, share').
- Slashes between words ('cảm ơn / ủng hộ' -> 'cảm ơn và ủng hộ').
- Grammar collisions caused by clause stitching ('sẽ Hãy cùng' -> 'sẽ cùng').
"""
import re
from typing import Any, Dict, List


def _replace_cased(text: str, pattern: re.Pattern, repl_upper: str, repl_lower: str) -> str:
    def _sub(m: re.Match) -> str:
        s = m.group(0)
        return repl_upper if s[0].isupper() else repl_lower
    return pattern.sub(_sub, text)


# Slashed pronouns: anh/chị, ông/bà, cô/chú, bạn/quý vị, quý vị/các bạn, etc.
SLASHED_PRONOUN_RULES = [
    (re.compile(r'\b[Aa]nh\s*/\s*[Cc]hị\b'), 'Các bạn', 'các bạn'),
    (re.compile(r'\b[Ôô]ng\s*/\s*[Bb]à\b'), 'Mọi người', 'mọi người'),
    (re.compile(r'\b[Cc]ô\s*/\s*[Cc]hú\b'), 'Mọi người', 'mọi người'),
    (re.compile(r'\b[Bb]ạn\s*/\s*[Qq]uý vị\b', re.IGNORECASE), 'Các bạn', 'các bạn'),
    (re.compile(r'\b[Qq]uý vị\s*/\s*[Bb]ạn\b', re.IGNORECASE), 'Các bạn', 'các bạn'),
    (re.compile(r'\b[Aa]nh\s+hoặc\s+chị\b', re.IGNORECASE), 'Các bạn', 'các bạn'),
    (re.compile(r'\b[Bb]ạn\s*/\s*[Cc]ác bạn\b', re.IGNORECASE), 'Các bạn', 'các bạn'),
]

# Social media / tech jargon literal translations
TECH_JARGON_PATTERNS = [
    # long-press, long‑press, long press (handling standard hyphen \u002d and non-breaking hyphen \u2011)
    (re.compile(r'\blong[\-‑\s]*press\b', re.IGNORECASE), 'nhấn giữ nút like'),
    (re.compile(r'\blike\s*,\s*share\b', re.IGNORECASE), 'like và chia sẻ'),
    (re.compile(r'\blike\s+share\b', re.IGNORECASE), 'like và chia sẻ'),
    (re.compile(r'\bshare\s*,\s*like\b', re.IGNORECASE), 'chia sẻ và like'),
    (re.compile(r'\blike\s*,\s*sub\b', re.IGNORECASE), 'like và đăng ký kênh'),
    (re.compile(r'\bnhấn giữ,\s*like\b', re.IGNORECASE), 'nhấn giữ nút like'),
]

# Literal channel name translations (e.g. 星河 -> Star River)
CHANNEL_NAME_PATTERNS = [
    (re.compile(r'\bHôm nay,\s*Star\s*River\s*sẽ\b', re.IGNORECASE), 'Hôm nay mình sẽ'),
    (re.compile(r'\bHôm nay\s*Star\s*River\s*sẽ\b', re.IGNORECASE), 'Hôm nay mình sẽ'),
    (re.compile(r'\bStar\s*River\b', re.IGNORECASE), 'kênh'),
]

# Collisions when stitching clauses
COLLISION_PATTERNS = [
    (re.compile(r'\bsẽ\s+[Hh]ãy\s+cùng\b'), 'sẽ cùng'),
    (re.compile(r'\bsẽ\s+hãy\s+cùng\b', re.IGNORECASE), 'sẽ cùng'),
    (re.compile(r'\bsẽ\s+[Hh]ãy\b'), 'sẽ'),
    (re.compile(r'\b[Hh]ãy\s+sẽ\b'), 'hãy'),
    (re.compile(r'\bđang\s+[Hh]ãy\b'), 'đang'),
    (re.compile(r'\bmuốn\s+[Hh]ãy\b'), 'muốn'),
    (re.compile(r'\bcùng\s+các bạn\s+các bạn\b', re.IGNORECASE), 'cùng các bạn'),
    (re.compile(r'\bcác bạn\s+các bạn\b', re.IGNORECASE), 'các bạn'),
    (re.compile(r'\bmọi người\s+mọi người\b', re.IGNORECASE), 'mọi người'),
]

# Slash between words (e.g. "Cảm ơn / ủng hộ" -> "Cảm ơn và ủng hộ")
INLINE_SLASH_PATTERN = re.compile(r'(\b[\w\u00C0-\u1EF9]+)\s*/\s*([\w\u00C0-\u1EF9]+\b)')


def sanitize_spoken_vietnamese(text: str) -> str:
    """Sanitize and humanize raw translated text into natural spoken Vietnamese for dubbing."""
    if not text:
        return ""

    out = text

    # 1. Replace literal English channel names first
    for pat, rep in CHANNEL_NAME_PATTERNS:
        out = pat.sub(rep, out)

    # 2. Replace slashed pronouns preserving capitalization
    for pat, upper_rep, lower_rep in SLASHED_PRONOUN_RULES:
        out = _replace_cased(out, pat, upper_rep, lower_rep)

    # 3. Replace tech jargon & Douyin literal translations
    for pat, rep in TECH_JARGON_PATTERNS:
        out = pat.sub(rep, out)

    # 4. Replace arbitrary slashes between words
    out = INLINE_SLASH_PATTERN.sub(r'\1 và \2', out)

    # 5. Fix grammar collisions
    for pat, rep in COLLISION_PATTERNS:
        out = pat.sub(rep, out)

    # 6. Normalize multiple spaces
    out = re.sub(r'[ \t]+', ' ', out).strip()

    # 7. Clean dangling single slashes remaining
    out = re.sub(r'\s*/\s*', ' ', out).strip()

    # 8. Clean half-translated CJK idioms and strip residual Chinese characters
    out = re.sub(r'\bkhó\s*[\u4e00-\u9fff\u3400-\u4dbf]+', 'khó khăn', out, flags=re.IGNORECASE)
    out = re.sub(r'\bnan\s*[\u4e00-\u9fff\u3400-\u4dbf]+', 'nan giải', out, flags=re.IGNORECASE)
    out = re.sub(r'[\u4e00-\u9fff\u3400-\u4dbf]+', '', out)

    # 9. Final whitespace normalization
    out = re.sub(r'[ \t]+', ' ', out).strip()

    return out


def is_translation_contaminated(text: str) -> bool:
    """Detect if a cached or generated translation has unacceptable machine artifacts."""
    if not text:
        return False
    lower = text.lower()
    if 'anh/chị' in lower or 'anh / chị' in lower:
        return True
    if 'ông/bà' in lower or 'cô/chú' in lower:
        return True
    if 'star river' in lower:
        return True
    if 'long-press' in lower or 'long‑press' in lower or 'long press' in lower:
        return True
    if ' / ' in text:
        return True
    if 'sẽ hãy cùng' in lower:
        return True
    if re.search(r'[\u4e00-\u9fff\u3400-\u4dbf]', text):
        return True
    return False


def clean_segments_spoken(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Clean all text fields across segments list."""
    for s in segments:
        for f in ("vi_text", "tts_text", "vi"):
            if f in s and isinstance(s[f], str):
                s[f] = sanitize_spoken_vietnamese(s[f])
    return segments
