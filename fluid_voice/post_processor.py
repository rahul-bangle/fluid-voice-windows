"""
fluid_voice.post_processor
--------------------------
Lightweight, deterministic Hinglish text post-processor.
Zero external dependencies, fast execution for live dictation.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Set

logger = logging.getLogger(__name__)


def double_metaphone(word: str) -> Tuple[str, str]:
    """
    Pure Python Double Metaphone algorithm.
    Returns a tuple of (primary_code, secondary_code).
    """
    if not word:
        return ("", "")

    s = "".join(c for c in word.upper() if c.isalpha())
    if not s:
        return ("", "")

    length = len(s)
    primary = []
    secondary = []
    current = 0

    if s.startswith(("GN", "KN", "PN", "WR", "PS")):
        current += 1

    if s.startswith("X"):
        primary.append("S")
        secondary.append("S")
        current += 1

    while current < length and (len(primary) < 4 or len(secondary) < 4):
        ch = s[current]

        if ch in "AEIOUY":
            if current == 0:
                primary.append("A")
                secondary.append("A")
            current += 1
        elif ch == "B":
            primary.append("P")
            secondary.append("P")
            current += 2 if (current + 1 < length and s[current + 1] == "B") else 1
        elif ch == "C":
            if current + 1 < length and s[current + 1] == "H":
                if current > 0 and s[current - 1] in "AEIOUY" and (current + 2 >= length or s[current + 2] not in "AEIOUY"):
                    primary.append("K")
                    secondary.append("K")
                else:
                    primary.append("X")
                    secondary.append("X")
                current += 2
            elif current + 1 < length and s[current + 1] in "IEY":
                primary.append("S")
                secondary.append("S")
                current += 2
            elif current + 1 < length and s[current + 1] == "K":
                primary.append("K")
                secondary.append("K")
                current += 2
            elif current + 1 < length and s[current + 1] == "C":
                primary.append("K")
                secondary.append("S")
                current += 2
            else:
                primary.append("K")
                secondary.append("K")
                current += 1
        elif ch == "D":
            if current + 1 < length and s[current + 1] == "G":
                if current + 2 < length and s[current + 2] in "IEY":
                    primary.append("J")
                    secondary.append("J")
                    current += 3
                else:
                    primary.append("TK")
                    secondary.append("TK")
                    current += 2
            else:
                primary.append("T")
                secondary.append("T")
                current += 2 if (current + 1 < length and s[current + 1] in "DT") else 1
        elif ch in "F":
            primary.append("F")
            secondary.append("F")
            current += 2 if (current + 1 < length and s[current + 1] == "F") else 1
        elif ch == "G":
            if current + 1 < length and s[current + 1] == "H":
                if current > 0 and s[current - 1] not in "AEIOUY":
                    primary.append("K")
                    secondary.append("K")
                current += 2
            elif current + 1 < length and s[current + 1] == "N":
                primary.append("N")
                secondary.append("N")
                current += 2
            elif current + 1 < length and s[current + 1] in "IEY":
                primary.append("J")
                secondary.append("K")
                current += 2
            else:
                primary.append("K")
                secondary.append("K")
                current += 2 if (current + 1 < length and s[current + 1] == "G") else 1
        elif ch == "H":
            if (current == 0 or s[current - 1] in "AEIOUY") and current + 1 < length and s[current + 1] in "AEIOUY":
                primary.append("H")
                secondary.append("H")
            current += 1
        elif ch == "J":
            primary.append("J")
            secondary.append("H")
            current += 2 if (current + 1 < length and s[current + 1] == "J") else 1
        elif ch == "K":
            primary.append("K")
            secondary.append("K")
            current += 2 if (current + 1 < length and s[current + 1] == "K") else 1
        elif ch == "L":
            primary.append("L")
            secondary.append("L")
            current += 2 if (current + 1 < length and s[current + 1] == "L") else 1
        elif ch == "M":
            primary.append("M")
            secondary.append("M")
            current += 2 if (current + 1 < length and s[current + 1] == "M") else 1
        elif ch == "N":
            primary.append("N")
            secondary.append("N")
            current += 2 if (current + 1 < length and s[current + 1] == "N") else 1
        elif ch == "P":
            if current + 1 < length and s[current + 1] == "H":
                primary.append("F")
                secondary.append("F")
                current += 2
            else:
                primary.append("P")
                secondary.append("P")
                current += 2 if (current + 1 < length and s[current + 1] == "P") else 1
        elif ch == "Q":
            primary.append("K")
            secondary.append("K")
            current += 2 if (current + 1 < length and s[current + 1] == "Q") else 1
        elif ch == "R":
            primary.append("R")
            secondary.append("R")
            current += 2 if (current + 1 < length and s[current + 1] == "R") else 1
        elif ch == "S":
            if current + 1 < length and s[current + 1] == "H":
                primary.append("X")
                secondary.append("X")
                current += 2
            elif current + 1 < length and s[current + 1] in "Z":
                primary.append("S")
                secondary.append("S")
                current += 2
            else:
                primary.append("S")
                secondary.append("S")
                current += 1
        elif ch == "T":
            if current + 1 < length and s[current + 1] == "H":
                primary.append("0")
                secondary.append("T")
                current += 2
            elif current + 1 < length and s[current + 1] in "IO" and current + 2 < length and s[current + 2] in "AEIOU":
                primary.append("X")
                secondary.append("X")
                current += 2
            else:
                primary.append("T")
                secondary.append("T")
                current += 2 if (current + 1 < length and s[current + 1] in "TT") else 1
        elif ch == "V":
            primary.append("F")
            secondary.append("F")
            current += 2 if (current + 1 < length and s[current + 1] == "V") else 1
        elif ch == "W":
            if current + 1 < length and s[current + 1] in "AEIOUY":
                primary.append("W")
                secondary.append("F")
            current += 1
        elif ch == "X":
            primary.append("KS")
            secondary.append("KS")
            current += 2 if (current + 1 < length and s[current + 1] == "X") else 1
        elif ch == "Y":
            if current + 1 < length and s[current + 1] in "AEIOU":
                primary.append("Y")
                secondary.append("Y")
            current += 1
        elif ch == "Z":
            primary.append("S")
            secondary.append("S")
            current += 2 if (current + 1 < length and s[current + 1] == "Z") else 1
        else:
            current += 1

    p_str = "".join(primary)[:4]
    s_str = "".join(secondary)[:4]
    return (p_str, s_str)


def jaro_winkler_distance(s1: str, s2: str, p: float = 0.1) -> float:
    """
    Calculates Jaro-Winkler similarity distance between two strings.
    Returns float between 0.0 and 1.0.
    """
    if s1 == s2:
        return 1.0
    if not s1 or not s2:
        return 0.0

    len1, len2 = len(s1), len(s2)
    match_distance = max(len1, len2) // 2 - 1
    if match_distance < 0:
        match_distance = 0

    s1_matches = [False] * len1
    s2_matches = [False] * len2

    matches = 0
    transpositions = 0

    for i in range(len1):
        start = max(0, i - match_distance)
        end = min(i + match_distance + 1, len2)
        for j in range(start, end):
            if s2_matches[j]:
                continue
            if s1[i] != s2[j]:
                continue
            s1_matches[i] = True
            s2_matches[j] = True
            matches += 1
            break

    if matches == 0:
        return 0.0

    k = 0
    for i in range(len1):
        if not s1_matches[i]:
            continue
        while not s2_matches[k]:
            k += 1
        if s1[i] != s2[k]:
            transpositions += 1
        k += 1

    jaro = (matches / len1 + matches / len2 + (matches - transpositions / 2.0) / matches) / 3.0

    prefix_len = 0
    for i in range(min(4, len1, len2)):
        if s1[i] == s2[i]:
            prefix_len += 1
        else:
            break

    return jaro + prefix_len * p * (1.0 - jaro)


from functools import lru_cache


@lru_cache(maxsize=4096)
def _get_metaphone_set(word: str) -> Set[str]:
    """Helper to extract non-empty metaphone keys for a word (cached)."""
    if not word:
        return set()
    p, s = double_metaphone(word)
    return {p, s} - {""}


COMMON_STOP_WORDS = {
    "the", "be", "to", "of", "and", "a", "in", "that", "have", "i", "it", "for", "not", "on", "with",
    "he", "as", "you", "do", "at", "this", "but", "his", "by", "from", "they", "we", "say", "her",
    "she", "or", "an", "will", "my", "one", "all", "would", "there", "their", "what", "so", "up",
    "out", "if", "about", "who", "get", "which", "go", "me", "when", "make", "can", "like", "time",
    "no", "just", "him", "know", "take", "people", "into", "year", "your", "good", "some", "could",
    "them", "see", "other", "than", "then", "now", "look", "only", "come", "its", "over", "think",
    "also", "back", "after", "use", "two", "how", "our", "work", "first", "well", "way", "even",
    "new", "want", "because", "any", "these", "give", "day", "most", "us", "is", "are", "was",
    "were", "has", "had", "been", "thing", "things", "general", "channel", "check", "number",
    "revert", "asap", "name", "bhai", "please"
}


def _build_lexicon_index(lexicon_map: Dict[str, str]) -> List[Dict[str, Any]]:
    """Helper to pre-compile lexicon metaphones and clean string representations."""
    indexed = []
    for key, canonical in lexicon_map.items():
        key_clean = "".join(c for c in key.lower() if c.isalnum())
        can_clean = "".join(c for c in canonical.lower() if c.isalnum())
        key_meta = _get_metaphone_set(key_clean)
        can_meta = _get_metaphone_set(can_clean)
        target_meta = (key_meta | can_meta) - {""}
        indexed.append({
            "key": key,
            "canonical": canonical,
            "key_clean": key_clean,
            "can_clean": can_clean,
            "key_lower": key.lower(),
            "target_meta": target_meta,
            "is_multiword": " " in key.strip(),
        })
    return indexed


def resolve_phonetic_mishears(
    text: str, lexicon_map: Optional[Dict[str, str]] = None, indexed_lexicon: Optional[List[Dict[str, Any]]] = None
) -> str:
    """
    Phonetic mishear resolution using Double Metaphone and Jaro-Winkler distance.
    Filters out empty string metaphone codes (`set() - {""}`).
    Preserves attached leading/trailing punctuation (e.g. "pie cut," -> "PyQt6,").
    Strictly guards against over-eager mishear corruptions of common English words.
    """
    if indexed_lexicon is None:
        if lexicon_map is None:
            lexicon_map = HinglishPostProcessor.BRAND_MAP

        full_lexicon = dict(lexicon_map)
        full_lexicon.setdefault("pie cut", "PyQt6")
        full_lexicon.setdefault("graph kewl", "GraphQL")
        full_lexicon.setdefault("graphql", "GraphQL")

        indexed_lexicon = _build_lexicon_index(full_lexicon)

    if "\n" in text:
        lines = text.split("\n")
        processed_lines = [resolve_phonetic_mishears(line, lexicon_map, indexed_lexicon) for line in lines]
        return "\n".join(processed_lines)

    tokens = text.split()
    if not tokens:
        return text

    def split_punct(token: str) -> Tuple[str, str, str]:
        match = re.match(r"^(\W*)(.*?)(\W*)$", token)
        if match:
            return match.group(1), match.group(2), match.group(3)
        return "", token, ""

    i = 0
    new_tokens = []
    while i < len(tokens):
        # 1. Try 2-word n-gram match first
        if i + 1 < len(tokens):
            lead1, core1, trail1 = split_punct(tokens[i])
            lead2, core2, trail2 = split_punct(tokens[i + 1])
            core1_clean = "".join(c for c in core1.lower() if c.isalnum())
            core2_clean = "".join(c for c in core2.lower() if c.isalnum())
            phrase_clean = (core1_clean + " " + core2_clean).strip()
            phrase_concat = (core1_clean + core2_clean).strip()

            if len(phrase_concat) >= 4:
                m1 = _get_metaphone_set(core1_clean)
                m2 = _get_metaphone_set(core2_clean)
                phrase_meta = ({p1 + p2 for p1 in m1 for p2 in m2} | m1 | m2) - {""}

                matched = False
                for item in indexed_lexicon:
                    key_clean = item["key_clean"]
                    can_clean = item["can_clean"]
                    key_lower = item["key_lower"]

                    # Exact phrase match check
                    if phrase_clean == key_lower or phrase_concat == can_clean or phrase_clean == key_clean:
                        replacement = f"{lead1}{item['canonical']}{trail2}"
                        new_tokens.append(replacement)
                        i += 2
                        matched = True
                        break

                    # If core1 or core2 alone matches this canonical item, do not let n-gram absorb the other word
                    if core1_clean == key_clean or core1_clean == can_clean or core2_clean == key_clean or core2_clean == can_clean:
                        continue

                    # Fast pre-filter: skip stop words & short phrases
                    if core1_clean in COMMON_STOP_WORDS and core2_clean in COMMON_STOP_WORDS:
                        continue

                    common_meta = (phrase_meta & item["target_meta"]) - {""}
                    if not common_meta:
                        continue

                    # Require at least one metaphone key of length >= 3 to avoid single-letter collisions ("A", "K")
                    if not any(len(m) >= 3 for m in common_meta):
                        continue

                    jw_text = jaro_winkler_distance(phrase_concat, can_clean)
                    jw_key = jaro_winkler_distance(phrase_clean, key_lower)

                    # Length ratio & diff guard
                    max_len = max(len(phrase_concat), len(can_clean))
                    min_len = min(len(phrase_concat), len(can_clean))
                    ratio = min_len / max_len if max_len > 0 else 0
                    diff = abs(len(phrase_concat) - len(can_clean))

                    if (jw_text >= 0.88 or jw_key >= 0.85) and ratio >= 0.65 and diff <= 3:
                        replacement = f"{lead1}{item['canonical']}{trail2}"
                        new_tokens.append(replacement)
                        i += 2
                        matched = True
                        break

                if matched:
                    continue

        # 2. Try single word match
        lead, core, trail = split_punct(tokens[i])
        core_lower = core.lower()
        core_clean = "".join(c for c in core_lower if c.isalnum())

        if core_clean and len(core_clean) >= 3:
            matched = False
            for item in indexed_lexicon:
                if item["is_multiword"]:
                    continue

                key_clean = item["key_clean"]
                can_clean = item["can_clean"]

                # Exact match check
                if core_clean == key_clean or core_clean == can_clean:
                    new_tokens.append(f"{lead}{item['canonical']}{trail}")
                    i += 1
                    matched = True
                    break

                # Fast pre-filter: skip stop words & non-ASCII/Devanagari script
                if core_clean in COMMON_STOP_WORDS or any(ord(c) > 127 for c in core):
                    continue

                word_meta = _get_metaphone_set(core_clean) - {""}
                common_meta = (word_meta & item["target_meta"]) - {""}
                if not common_meta:
                    continue

                # Metaphone code length guard (must be >= 3)
                if not any(len(m) >= 3 for m in common_meta):
                    continue

                jw_text = jaro_winkler_distance(core_clean, can_clean)
                jw_key = jaro_winkler_distance(core_clean, key_clean)

                # Length ratio & diff guard
                max_len = max(len(core_clean), len(can_clean))
                min_len = min(len(core_clean), len(can_clean))
                ratio = min_len / max_len if max_len > 0 else 0
                diff = abs(len(core_clean) - len(can_clean))

                if (jw_text >= 0.88 or jw_key >= 0.85) and ratio >= 0.65 and diff <= 3:
                    new_tokens.append(f"{lead}{item['canonical']}{trail}")
                    i += 1
                    matched = True
                    break

            if matched:
                continue

        # Default single token advance (FIXED: single append & increment)
        new_tokens.append(tokens[i])
        i += 1

    return " ".join(new_tokens)


SPOKEN_ACTION_TRIGGERS = [
    "jarvis send",
    "jarvis enter",
    "computer send",
    "computer enter",
]


def parse_spoken_action(text: str) -> Tuple[str, Optional[str]]:
    """
    Parses spoken action commands like 'Jarvis send', 'Jarvis enter', 'computer enter', 'computer send'.
    Returns a tuple of (cleaned_payload_text, action_name), where action_name is 'VK_RETURN' if found, else None.
    """
    if not text:
        return ("", None)

    raw_text = text.strip()
    if not raw_text:
        return ("", None)

    matched_action = None
    cleaned = raw_text

    for trigger in SPOKEN_ACTION_TRIGGERS:
        pattern = re.compile(rf"(?:^|[\s,.:;!])({trigger})(?:[\s,.:;!]|$)", re.IGNORECASE)
        match = pattern.search(cleaned)
        if match:
            matched_action = "VK_RETURN"
            cleaned = pattern.sub(" ", cleaned)
            break

    if matched_action is not None:
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        cleaned = re.sub(r"^[\s,.:;!]+|[\s,.:;!]+$", "", cleaned).strip()
        return (cleaned, matched_action)

    return (raw_text, None)


JARVIS_ACTIVATION_TRIGGERS = [
    "jarvis type",
    "jarvis start",
    "start typing",
    "computer type",
    "type",
    "typing",
    "taping",
]

JARVIS_PAUSE_TRIGGERS = [
    "jarvis pause",
    "jarvis stop",
    "stop typing",
    "computer stop",
    "jarvis paz",
    "jarvis pass",
    "jarvis path",
    "stop taping",
    "pause typing",
    "pause",
]


def parse_jarvis_trigger(text: str, is_active: bool) -> Tuple[str, bool, Optional[str]]:
    """
    Parses Jarvis Callout / Standby triggers.
    - Activation triggers ("Type", "Jarvis type", "Start typing"): Wakes up Jarvis to active listening/typing mode.
    - Deactivation triggers ("Jarvis pause", "Jarvis stop", "Jarvis paz", "Stop typing"): Puts Jarvis back to standby mode.
    Returns (cleaned_text, new_is_active_state, status_event_str).
    """
    if not text or not text.strip():
        return ("", is_active, None)

    raw_text = text.strip()

    # Check pause/standby triggers first
    for p_trig in JARVIS_PAUSE_TRIGGERS:
        pattern = re.compile(rf"(?:^|[\s,.:;!])({p_trig})(?:[\s,.:;!]|$)", re.IGNORECASE)
        match = pattern.search(raw_text)
        if match:
            cleaned = pattern.sub(" ", raw_text)
            cleaned = re.sub(r"\s+", " ", cleaned).strip()
            cleaned = re.sub(r"^[\s,.:;!]+|[\s,.:;!]+$", "", cleaned).strip()
            return (cleaned, False, "PAUSED")

    # If currently in Standby (is_active is False), check for activation triggers
    if not is_active:
        for a_trig in JARVIS_ACTIVATION_TRIGGERS:
            pattern = re.compile(rf"(?:^|[\s,.:;!])({a_trig})(?:[\s,.:;!]|$)", re.IGNORECASE)
            match = pattern.search(raw_text)
            if match:
                cleaned = pattern.sub(" ", raw_text)
                cleaned = re.sub(r"\s+", " ", cleaned).strip()
                cleaned = re.sub(r"^[\s,.:;!]+|[\s,.:;!]+$", "", cleaned).strip()
                return (cleaned, True, "ACTIVATED")
        # In standby and no activation trigger spoken -> IGNORE audio (prevents background noise typing)
        return ("", False, "IGNORED")

    # Already active, no pause trigger found -> continue typing
    return (raw_text, True, None)


class HinglishPostProcessor:
    """Post-processor for Hinglish voice dictation transcription."""

    DEFAULT_CONFIG = {
        "enable_disfluency_cleanup": True,
        "enable_voice_commands": True,
        "enable_idioms": True,
        "enable_brand_formatting": True,
        "enable_number_formatting": True,
        "indian_number_style": "hybrid",  # "hybrid" ("10 lakh") or "digits" ("10,00,000")
        "enable_currency_formatting": True,
        "enable_date_time_formatting": True,
        "enable_list_formatting": True,
        "enable_auto_punctuation": True,
        "enable_smart_capitalization": True,
    }

    BRAND_MAP = {
        "groq": "Groq",
        "whisper": "Whisper",
        "pyqt": "PyQt6",
        "pyqt6": "PyQt6",
        "graphql": "GraphQL",
        "vscode": "VS Code",
        "vs code": "VS Code",
        "notepad": "Notepad",
        "python": "Python",
        "windows": "Windows",
        "google": "Google",
        "microsoft": "Microsoft",
        "whatsapp": "WhatsApp",
        "slack": "Slack",
        "youtube": "YouTube",
        "linkedin": "LinkedIn",
        "paytm": "Paytm",
        "upi": "UPI",
        "zomato": "Zomato",
        "swiggy": "Swiggy",
        "flipkart": "Flipkart",
        "ola": "Ola",
        "uber": "Uber",
        "aadhaar": "Aadhaar",
        "pan card": "PAN card",
        "gst": "GST",
        "rbi": "RBI",
        "sbi": "SBI",
        "hdfc": "HDFC",
        "icici": "ICICI",
        "delhi": "Delhi",
        "mumbai": "Mumbai",
        "bangalore": "Bengaluru",
        "bengaluru": "Bengaluru",
        "hyderabad": "Hyderabad",
        "chennai": "Chennai",
        "kolkata": "Kolkata",
        "pune": "Pune",
    }

    COMMAND_DICT = {
        "new paragraph": "\n\n",
        "next paragraph": "\n\n",
        "new line": "\n",
        "next line": "\n",
        "full stop": ".",
        "period": ".",
        "comma": ",",
        "question mark": "?",
        "colon": ":",
        "semi colon": ";",
        "semicolon": ";",
        "open bracket": "(",
        "close bracket": ")",
        "open quote": '"',
        "close quote": '"',
    }

    IDIOM_DICT = {
        "do one thing": "do one thing,",
        "prepone": "reschedule",
        "revert back": "revert",
        "up to mark": "up to the mark",
        "discuss about": "discuss",
        "out of station": "out of station",
        "years back": "years ago",
        "pass out from": "graduate from",
        "good name": "name",
        "same to you": "same to you.",
    }

    HINGLISH_VOCAB_MAP = {
        "haa": "haan",
        "acha": "accha",
        "thik": "theek",
        "samajh": "samjha",
    }

    ORDINAL_LIST_MAP = {
        "firstly": "1.",
        "secondly": "\n2.",
        "thirdly": "\n3.",
        "fourthly": "\n4.",
        "fifthly": "\n5.",
    }

    SPOKEN_NUMBERS = {
        "ek": "1", "one": "1",
        "do": "2", "two": "2",
        "teen": "3", "three": "3",
        "char": "4", "chaar": "4", "four": "4",
        "paanch": "5", "panch": "5", "five": "5",
        "chhe": "6", "six": "6",
        "saat": "7", "seven": "7",
        "aath": "8", "eight": "8",
        "nau": "9", "nine": "9",
        "dus": "10", "das": "10", "ten": "10",
        "pachas": "50", "fifty": "50",
        "sau": "100", "hundred": "100"
    }

    HINDI_QUESTION_WORDS = {
        "kya", "kaha", "kahan", "kab", "kyun", "kyu", "kaise", "kaun",
        "\u0915\u094D\u092F\u093E",
        "\u0915\u0939\u093E\u0902",
        "\u0915\u092C",
        "\u0915\u094D\u092F\u094B\u0902",
        "\u0915\u0948\u0938\u0947",
        "\u0915\u094C\u0928",
    }

    ENGLISH_QUESTION_STARTERS = {
        "what", "where", "when", "why", "how", "who", "which", "can", "could", "would", "is", "are", "do", "does", "did", "should"
    }

    MONTHS = (
        "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december"
    )

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}
        self._compile_regexes()

    def _compile_regexes(self) -> None:
        self.re_spaces = re.compile(r"[ \t]+")
        self.re_punct_spaces = re.compile(r"[ \t]+([,.?!:;])")
        self.re_disfluencies = re.compile(r"\b(uh|um|uhh|umm)\b", re.IGNORECASE)
        self.re_stutter = re.compile(r"\b(\w+)(?:\s+\1)+\b", re.IGNORECASE)

        # Commands pattern
        sorted_cmds = sorted(self.COMMAND_DICT.keys(), key=len, reverse=True)
        self.re_commands = re.compile(r"\b(" + "|".join(re.escape(k) for k in sorted_cmds) + r")\b", re.IGNORECASE)

        # Idioms pattern
        sorted_idioms = sorted(self.IDIOM_DICT.keys(), key=len, reverse=True)
        self.re_idioms = re.compile(r"\b(" + "|".join(re.escape(k) for k in sorted_idioms) + r")\b", re.IGNORECASE)

        # Brand regex pattern
        sorted_brands = sorted(self.BRAND_MAP.keys(), key=len, reverse=True)
        self.re_brands = re.compile(r"\b(" + "|".join(re.escape(k) for k in sorted_brands) + r")\b", re.IGNORECASE)

        # Hinglish Vocab pattern
        sorted_vocab = sorted(self.HINGLISH_VOCAB_MAP.keys(), key=len, reverse=True)
        self.re_vocab = re.compile(r"\b(" + "|".join(re.escape(k) for k in sorted_vocab) + r")\b", re.IGNORECASE)

        # Months pattern
        self.re_months = re.compile(r"\b(" + "|".join(self.MONTHS) + r")\b", re.IGNORECASE)

        # Ordinal lists pattern
        self.re_ordinal_lists = re.compile(r"\b(firstly|secondly|thirdly|fourthly|fifthly)\b", re.IGNORECASE)

        # Spoken number pattern before units
        num_words = "|".join(re.escape(k) for k in self.SPOKEN_NUMBERS.keys())
        self.re_spoken_unit = re.compile(rf"\b({num_words})\s+(lakh|lakhs|lac|lacs|crore|crores|thousand|hazar|hundred)\b", re.IGNORECASE)

        # Number patterns
        self.re_hundred = re.compile(r"\b(\d+)\s*hundred\b", re.IGNORECASE)
        self.re_thousand = re.compile(r"\b(\d+)\s*(?:thousand|hazar)\b", re.IGNORECASE)
        self.re_lakh = re.compile(r"\b(\d+)\s*(?:lakh|lakhs|lac|lacs)\b", re.IGNORECASE)
        self.re_crore = re.compile(r"\b(\d+)\s*(?:crore|crores)\b", re.IGNORECASE)
        self.re_percent = re.compile(r"\b(\d+)\s*(?:percent|per cent|%)\b", re.IGNORECASE)

        # Currency
        self.re_rs_prefix = re.compile(r"\b(?:rs|rs\.|rupees)\s*(\d+(?:,\d+)*(?:\.\d+)?(?:\s*(?:lakh|lakhs|crore|crores|thousand|hazar))?)\b", re.IGNORECASE)
        self.re_rs_suffix = re.compile(r"\b(\d+(?:,\d+)*(?:\.\d+)?(?:\s*(?:lakh|lakhs|crore|crores|thousand|hazar))?)\s*(?:rs|rs\.|rupees)\b", re.IGNORECASE)

        # Devanagari boundary spacing
        self.re_dev_latin1 = re.compile(r"([\u0900-\u097F])([a-zA-Z0-9])")
        self.re_dev_latin2 = re.compile(r"([a-zA-Z0-9])([\u0900-\u097F])")

    WHISPER_HALLUCINATIONS = (
        "murshid",
        "karahiya",
        "hosh meh",
        "hosh me",
        "subtitles by",
        "amara.org",
        "thanks for watching",
        "thank you for watching",
    )

    def clean_hallucinations(self, text: str) -> str:
        """Strips Whisper ASR tail hallucinations while preserving legitimate user dictation."""
        if not text or not text.strip():
            return ""

        clean = text.strip()
        lower_clean = clean.lower()

        # If the entire text is just a hallucination phrase, return ""
        for h in self.WHISPER_HALLUCINATIONS:
            if lower_clean.strip(".,!?;:\"' ") == h or lower_clean == h:
                return ""

        # Strip hallucination phrases embedded or appended at the end
        for h in self.WHISPER_HALLUCINATIONS:
            pattern = re.compile(rf"(?:[\s,.:;!]|\b){re.escape(h)}(?:[\s,.:;!]|$)", re.IGNORECASE)
            clean = pattern.sub(" ", clean)

        clean = re.sub(r"\s+", " ", clean).strip()
        return clean

    def process(self, raw_text: str) -> str:
        """Transform raw Whisper STT output into formatted, clean text."""
        if not raw_text or not raw_text.strip():
            return ""

        text = self.clean_hallucinations(raw_text)
        if not text:
            return ""

        # Pass 1: Whitespace & Disfluency Normalization
        if self.config.get("enable_disfluency_cleanup", True):
            text = self._pass_whitespace_disfluency(text)

        # Pass 2: Voice Dictation Commands & Indian English Idioms
        if self.config.get("enable_voice_commands", True) or self.config.get("enable_idioms", True):
            text = self._pass_commands_and_idioms(text)

        # Pass 3: Brand Names & Mixed Hinglish Script
        if self.config.get("enable_brand_formatting", True):
            text = self._pass_brands_and_hinglish(text)

        # Pass 4: Numbers, Currency, Dates & Times
        if self.config.get("enable_number_formatting", True):
            text = self._pass_numbers_currency_dates(text)

        # Pass 5: Bullet Point & List Auto-Formatting
        if self.config.get("enable_list_formatting", True):
            text = self._pass_lists(text)

        # Pass 6: Sentence Boundaries, Capitalization & Punctuation Polish
        if self.config.get("enable_smart_capitalization", True) or self.config.get("enable_auto_punctuation", True):
            text = self._pass_punctuation_and_capitalization(text)

        return text.strip()

    def _pass_whitespace_disfluency(self, text: str) -> str:
        text = self.re_disfluencies.sub("", text)
        text = self.re_stutter.sub(r"\1", text)
        text = self.re_punct_spaces.sub(r"\1", text)
        text = self.re_spaces.sub(" ", text)
        return text.strip()

    def _pass_commands_and_idioms(self, text: str) -> str:
        if self.config.get("enable_voice_commands", True):
            text = self.re_commands.sub(lambda m: self.COMMAND_DICT.get(m.group(0).lower(), m.group(0)), text)

        if self.config.get("enable_idioms", True):
            text = self.re_idioms.sub(lambda m: self.IDIOM_DICT.get(m.group(0).lower(), m.group(0)), text)

        return text

    def _pass_brands_and_hinglish(self, text: str) -> str:
        def replace_brand(match):
            word_key = match.group(0).lower()
            return self.BRAND_MAP.get(word_key, match.group(0))

        text = self.re_brands.sub(replace_brand, text)

        # Double Metaphone + Jaro-Winkler phonetic mishear resolution (uses pre-compiled _indexed_lexicon)
        text = resolve_phonetic_mishears(text, self.BRAND_MAP, getattr(self, "_indexed_lexicon", None))

        text = self.re_vocab.sub(lambda m: self.HINGLISH_VOCAB_MAP.get(m.group(0).lower(), m.group(0)), text)

        # Devanagari script spacing cleanup
        text = self.re_dev_latin1.sub(r"\1 \2", text)
        text = self.re_dev_latin2.sub(r"\1 \2", text)

        return text

    def _pass_numbers_currency_dates(self, text: str) -> str:
        style = self.config.get("indian_number_style", "hybrid")

        # First replace spoken word numbers before units (e.g. "dus lakh" -> "10 lakh")
        text = self.re_spoken_unit.sub(
            lambda m: f"{self.SPOKEN_NUMBERS.get(m.group(1).lower(), m.group(1))} {m.group(2)}",
            text
        )

        # Currency formatting first ("500 rupees" -> "Rs 500", "15 lakh rupees" -> "Rs 15,00,000")
        if self.config.get("enable_currency_formatting", True):
            text = self.re_rs_prefix.sub(r"Rs \1", text)
            text = self.re_rs_suffix.sub(r"Rs \1", text)
            text = re.sub(r"Rs\s+(\d+)\s*(?:lakh|lakhs|lac|lacs)\b", lambda m: f"Rs {self._format_indian_digits(int(m.group(1)) * 100000)}", text, flags=re.IGNORECASE)
            text = re.sub(r"Rs\s+(\d+)\s*(?:crore|crores)\b", lambda m: f"Rs {self._format_indian_digits(int(m.group(1)) * 10000000)}", text, flags=re.IGNORECASE)

        # Number conversions
        text = self.re_hundred.sub(lambda m: str(int(m.group(1)) * 100), text)
        if style == "digits":
            text = self.re_thousand.sub(lambda m: self._format_indian_digits(int(m.group(1)) * 1000), text)
            text = self.re_lakh.sub(lambda m: self._format_indian_digits(int(m.group(1)) * 100000), text)
            text = self.re_crore.sub(lambda m: self._format_indian_digits(int(m.group(1)) * 10000000), text)
        else:
            text = self.re_thousand.sub(lambda m: f"{self._format_indian_digits(int(m.group(1)) * 1000)}", text)
            text = self.re_lakh.sub(r"\1 lakh", text)
            text = self.re_crore.sub(r"\1 crore", text)

        text = self.re_percent.sub(r"\1%", text)

        # Date & Time formatting (months capitalization & 3 PM -> 3:00 PM)
        if self.config.get("enable_date_time_formatting", True):
            text = re.sub(r"\b(\d{1,2})\s*(pm|am)\b", lambda m: f"{m.group(1)}:00 {m.group(2).upper()}", text, flags=re.IGNORECASE)
            text = self.re_months.sub(lambda m: m.group(0).capitalize(), text)

        return text

    def _format_indian_digits(self, n: int) -> str:
        s = str(n)
        if len(s) <= 3:
            return s
        last3 = s[-3:]
        other = s[:-3]
        res = ""
        while len(other) > 2:
            res = "," + other[-2:] + res
            other = other[:-2]
        return other + res + "," + last3

    def _pass_lists(self, text: str) -> str:
        # Format firstly, secondly, thirdly, etc.
        text = self.re_ordinal_lists.sub(lambda m: self.ORDINAL_LIST_MAP.get(m.group(0).lower(), m.group(0)), text)

        text = re.sub(r"(?<!\n)\bpoint\s+(\d+)\b", r"\n\1.", text, flags=re.IGNORECASE)
        text = re.sub(r"^\n", "", text)
        text = re.sub(r"(?<!\n)\bnumber\s+(\d+)\b", r"\n\1.", text, flags=re.IGNORECASE)
        text = re.sub(r"^\n", "", text)

        text = re.sub(r"\bnext bullet\b", "\n•", text, flags=re.IGNORECASE)
        text = re.sub(r"\bbullet\b", "•", text, flags=re.IGNORECASE)
        return text

    def _pass_punctuation_and_capitalization(self, text: str) -> str:
        if not text:
            return ""

        # Clean spaces around punctuation
        text = self.re_punct_spaces.sub(r"\1", text)
        # Trim space around newlines
        text = re.sub(r"[ \t]*\n[ \t]*", "\n", text)

        lines = text.split("\n")
        processed_lines = []
        for line in lines:
            line_str = line.strip()
            if not line_str:
                processed_lines.append("")
                continue

            # Question detection:
            words_in_line = [re.sub(r"\W", "", w).lower() for w in line_str.split() if re.sub(r"\W", "", w)]
            first_word = words_in_line[0] if words_in_line else ""

            is_question_starter = first_word in self.ENGLISH_QUESTION_STARTERS or first_word in self.HINDI_QUESTION_WORDS
            has_hindi_q_word = any(w in self.HINDI_QUESTION_WORDS for w in words_in_line) or any(
                qw in line_str for qw in ("\u0915\u094D\u092F\u093E", "\u0915\u0939\u093E\u0902", "\u0915\u092C", "\u0915\u094D\u092F\u094B\u0902", "\u0915\u0948\u0938\u0947", "\u0915\u094C\u0928")
            )

            is_question = is_question_starter or has_hindi_q_word

            if not line_str[-1] in ".?!;:":
                if is_question:
                    line_str += "?"
                else:
                    line_str += "."

            # Capitalize first letter of line
            if len(line_str) > 0 and line_str[0].isalpha():
                line_str = line_str[0].upper() + line_str[1:]

            processed_lines.append(line_str)

        text = "\n".join(processed_lines)

        # Capitalize after sentence terminators within paragraphs
        def cap_match(m):
            return m.group(1) + m.group(2).upper()

        text = re.sub(r"([.?!]\s+)([a-z])", cap_match, text)

        # Standing single letter "i" -> "I"
        text = re.sub(r"\bi\b", "I", text)

        return text

    def update_brand_map(self, custom_mappings: Dict[str, str]) -> None:
        """Dynamically updates fallback BRAND_MAP with user memory phonetic mappings."""
        if custom_mappings:
            for k, v in custom_mappings.items():
                if isinstance(k, str) and isinstance(v, str):
                    self.BRAND_MAP[k.strip().lower()] = v

    def process_with_groq_llm(
        self,
        raw_text: str,
        api_key: str,
        timeout: float = 2.5,
        context: Optional[Any] = None,
        context_prompt: Optional[str] = None,
        memory_hints: Optional[List[Any]] = None,
        memory_engine: Optional[Any] = None,
    ) -> str:
        """
        Stage 2 LLM Cleanup using Groq Llama 3.1 8B Instant.
        Converts any Devanagari script or translated English into clean Roman Hinglish.
        Optionally accepts active AppContext, context_prompt hint, memory_hints, or memory_engine.
        """
        if not raw_text or not raw_text.strip() or not api_key:
            return self.process(raw_text)

        if memory_engine is not None:
            try:
                self.update_brand_map(memory_engine.get_phonetic_mappings())
            except Exception as e:
                logger.warning(f"Failed to update brand map from memory_engine: {e}")

            if memory_hints is None:
                try:
                    memory_hints = memory_engine.get_relevant_memories(context=context, raw_text=raw_text, limit=8)
                except Exception as e:
                    logger.warning(f"Failed to retrieve relevant memories from memory_engine: {e}")
                    memory_hints = None

        system_prompt = (
            "You are a strict Verbatim Speech Punctuation & Formatting Engine. DO NOT ANSWER QUESTIONS OR CONVERSE.\n"
            "Format raw speech into clean text while preserving the user's EXACT spoken words, vocabulary, and tone.\n"
            "MANDATORY: DO NOT REWRITE WORDS, DO NOT REPHRASE, AND DO NOT CONVERT CASUAL LANGUAGE TO FORMAL LANGUAGE.\n"
            "Preserve every word spoken by the user exactly as uttered. Only fix basic punctuation, capitalization, and technical terms (code, push, PR, database, API, server, meeting, Docker).\n"
            "Output ONLY the exact formatted text with zero explanation."
        )

        if not context_prompt and context is not None:
            try:
                from fluid_voice.context_engine import ContextEngine
                context_prompt = ContextEngine().build_llm_context_prompt(context)
            except Exception as e:
                logger.warning(f"Could not build context prompt from context: {e}")

        if context_prompt:
            system_prompt += f"\nContext: {context_prompt}"

        if memory_hints:
            canonical_terms = [getattr(item, "term", str(item)) for item in memory_hints if hasattr(item, "term")]
            if canonical_terms:
                system_prompt += "\n\n8. USER PERSONAL LEXICON & JARGON HINTS:\n"
                system_prompt += f"Canonical Terms: {', '.join(canonical_terms)}\n"
                for item in memory_hints:
                    term = getattr(item, "term", None)
                    variants = getattr(item, "phonetic_variants", [])
                    if term and variants:
                        var_str = ", ".join(f'"{v}"' for v in variants)
                        system_prompt += f'- {var_str} -> "{term}"\n'
                system_prompt += "\n9. DISAMBIGUATION & CONTEXT SAFETY RULES:\n"
                system_prompt += "Do not rephrase or hallucinate beyond substituting spoken variants with their canonical terms."

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        # Calculate low-latency max_tokens cap based on raw transcript word count
        word_count = len(raw_text.strip().split())
        max_toks = max(32, min(256, word_count * 3 + 24))

        payload = {
            "model": "llama-3.1-8b-instant",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"TRANSCRIPT TO FORMAT:\n{raw_text}"}
            ],
            "temperature": 0.0,
            "max_tokens": max_toks,
        }

        try:
            import requests
            resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"].strip()
                if (content.startswith('"') and content.endswith('"')) or (content.startswith("'") and content.endswith("'")):
                    content = content[1:-1].strip()
                return self.process(content)
        except Exception as e:
            logger.warning(f"Groq Llama 3.1 LLM post-processing fallback to rule engine: {e}")

        return self.process(raw_text)


