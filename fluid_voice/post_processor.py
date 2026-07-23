"""
fluid_voice.post_processor
--------------------------
Lightweight, deterministic Hinglish text post-processor.
Zero external dependencies, fast execution for live dictation.
"""

import re
from typing import Any, Dict, List, Optional


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

    def process(self, raw_text: str) -> str:
        """Transform raw Whisper STT output into formatted, clean text."""
        if not raw_text or not raw_text.strip():
            return ""

        lower_raw = raw_text.lower()
        if any(h in lower_raw for h in self.WHISPER_HALLUCINATIONS):
            return ""

        text = raw_text

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
            canonical_terms = [getattr(item, "term", str(item)) for item in memory_hints]
            if canonical_terms:
                system_prompt += f"\nUser Jargon Lexicon: {', '.join(canonical_terms[:6])}"

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


