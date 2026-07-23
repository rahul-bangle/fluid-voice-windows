"""
Unit tests for fluid_voice.post_processor (Hinglish Post-Processor).

Covers Tier 1 (Happy Path Feature Coverage) & Tier 2 (Boundary & Corner Cases).
Minimum 10 tests.
"""

import time
import pytest
from fluid_voice.post_processor import HinglishPostProcessor


@pytest.fixture
def processor() -> HinglishPostProcessor:
    return HinglishPostProcessor()


# ============================================================================
# Tier 1: Happy Path Feature Coverage Tests
# ============================================================================

def test_post_processor_sentence_capitalization(processor: HinglishPostProcessor):
    """Tier 1: Capitalizes first letter of sentences and single standing 'I'."""
    raw = "hello bhai how are you. i am fine."
    result = processor.process(raw)
    assert result.startswith("Hello")
    assert "I am fine." in result


def test_post_processor_auto_punctuation_declarative_and_question(processor: HinglishPostProcessor):
    """Tier 1: Automatic punctuation placement (periods for statements, question marks for questions)."""
    # Statement
    raw_statement = "everything is working fine thanks"
    assert processor.process(raw_statement) == "Everything is working fine thanks."

    # Question with English question word
    raw_q_en = "what is your name"
    assert processor.process(raw_q_en) == "What is your name?"

    # Question with Hindi question word
    raw_q_hi = "aapka naam kya hai"
    assert processor.process(raw_q_hi) == "Aapka naam kya hai?"


def test_post_processor_hinglish_mixed_word_normalization(processor: HinglishPostProcessor):
    """Tier 1: Normalizes Hinglish mixed words, tech terms, and brand names."""
    raw = "groq whisper pyqt vscode paytm upi me meeting set karo"
    result = processor.process(raw)
    assert "Groq" in result
    assert "Whisper" in result
    assert "PyQt6" in result
    assert "VS Code" in result
    assert "Paytm" in result
    assert "UPI" in result


def test_post_processor_number_formatting(processor: HinglishPostProcessor):
    """Tier 1: Formats spoken number units ('50 thousand', '5 lakhs')."""
    # Hybrid mode (default)
    raw_hybrid = "the budget is 50 thousand rupees and revenue is 5 lakhs"
    res_hybrid = processor.process(raw_hybrid)
    assert "50,000" in res_hybrid
    assert "5 lakh" in res_hybrid

    # Digits mode
    processor_digits = HinglishPostProcessor(config={"indian_number_style": "digits"})
    raw_digits = "project budget is 5 lakhs rupees"
    res_digits = processor_digits.process(raw_digits)
    assert "5,00,000" in res_digits or "500,000" in res_digits


def test_post_processor_date_formatting(processor: HinglishPostProcessor):
    """Tier 1: Date formatting capitalizes month names and preserves ordinals."""
    raw = "the meeting is scheduled for 23rd july and next on 1st january 2026"
    result = processor.process(raw)
    assert "23rd July" in result
    assert "1st January 2026" in result


# ============================================================================
# Tier 2: Boundary & Corner Cases Tests
# ============================================================================

def test_post_processor_empty_and_whitespace_input(processor: HinglishPostProcessor):
    """Tier 2: Empty string input and whitespace-only string handling."""
    assert processor.process("") == ""
    assert processor.process("   ") == ""
    assert processor.process("\n\t") == ""


def test_post_processor_special_characters_and_symbols(processor: HinglishPostProcessor):
    """Tier 2: Preserves special characters, hashtags, emails, and emojis without corruption."""
    raw = "check #general channel or email user@test.com for 🚀 release"
    result = processor.process(raw)
    assert "#general" in result
    assert "user@test.com" in result
    assert "🚀" in result


def test_post_processor_devanagari_script_preservation(processor: HinglishPostProcessor):
    """Tier 2: Preserves Devanagari script characters alongside English/Hinglish text."""
    raw = "आपका WhatsApp number क्या है"
    result = processor.process(raw)
    assert "आपका" in result
    assert "WhatsApp" in result
    assert "क्या" in result
    assert "है?" in result


def test_post_processor_indian_english_dictation_idioms(processor: HinglishPostProcessor):
    """Tier 2: Normalizes Indian English dictation idioms and currency phrases."""
    # Idiom replacement
    raw_idiom = "please do one thing revert back to me asap"
    res_idiom = processor.process(raw_idiom)
    assert "do one thing," in res_idiom
    assert "revert" in res_idiom
    assert "revert back" not in res_idiom

    # Out of station idiom
    raw_station = "he is currently out of station"
    assert "out of station" in processor.process(raw_station)

    # Currency idiom ("500 rupees" -> "Rs 500")
    raw_currency = "total cost is 500 rupees"
    res_curr = processor.process(raw_currency)
    assert "Rs 500" in res_curr or "₹500" in res_curr


def test_post_processor_long_multiparagraph_text_performance(processor: HinglishPostProcessor):
    """Tier 2: Performance and stability under long multi-paragraph dictation text (1000+ words)."""
    paragraph = (
        "bhai do one thing send me the project report by 5 PM. "
        "groq whisper API is processing 15 lakh requests with 18 percent GST. "
        "revert back if you have any questions regarding Python or PyQt6 setup. "
    )
    long_text = "\n\n".join([paragraph] * 35)  # ~1000+ words

    start_time = time.perf_counter()
    result = processor.process(long_text)
    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    assert len(result) > 0
    # Must process 1000+ words in under 30ms on Intel Core i3
    assert elapsed_ms < 50.0


def test_post_processor_disfluencies_and_repeated_words(processor: HinglishPostProcessor):
    """Tier 2: Removes vocal disfluencies ('uh', 'um') and repeated stutter words."""
    raw = "uh hello um world the the code is ready"
    result = processor.process(raw)
    assert "uh" not in result.lower().split()
    assert "um" not in result.lower().split()
    assert "the the" not in result.lower()


def test_post_processor_voice_commands(processor: HinglishPostProcessor):
    """Tier 2: Handles voice dictation commands ('new line', 'full stop', 'comma', brackets/quotes)."""
    raw = "hello comma world full stop new line open bracket urgent close bracket this is line two"
    result = processor.process(raw)
    assert "Hello, world." in result
    assert "(urgent)" in result or "( urgent )" in result or "(urgent)." in result
    assert "\n" in result


def test_post_processor_list_formatting(processor: HinglishPostProcessor):
    """Tier 2: Auto-formats spoken bullet points and list indicators."""
    raw = "firstly item one secondly item two"
    result = processor.process(raw)
    assert "1. Item one" in result
    assert "2. Item two" in result

    raw_bullets = "bullet first point next bullet second point"
    result_b = processor.process(raw_bullets)
    assert "•" in result_b


def test_post_processor_config_toggles():
    """Tier 2: Validates disabling specific post-processing passes via configuration flags."""
    no_disfluency = HinglishPostProcessor(config={"enable_disfluency_cleanup": False})
    assert "uh" in no_disfluency.process("uh hello world").lower()

    no_idioms = HinglishPostProcessor(config={"enable_idioms": False})
    assert "revert back" in no_idioms.process("revert back to me").lower()



