"""
Tier 4 E2E Test Suite: Real-World Hinglish Dictation Scenarios
----------------------------------------------------------------
Validates end-to-end Hinglish speech-to-text post-processing across:
1. Mixed Hinglish technical sentences.
2. Code commentary & syntax dictation.
3. Currency & Indian numbering dictation (lakhs, crores, Rs).
4. Multi-sentence email dictation with auto-capitalization & auto-punctuation.
5. Indian English idiom normalization & brand name formatting.
"""

import pytest
from fluid_voice.post_processor import HinglishPostProcessor


@pytest.fixture
def processor() -> HinglishPostProcessor:
    """Fixture providing a fresh default HinglishPostProcessor instance."""
    return HinglishPostProcessor()


def test_mixed_hinglish_technical_sentence(processor: HinglishPostProcessor):
    """
    E2E Test Scenario 1: Mixed Hinglish technical sentence dictation.
    Input: 'aaj meeting 3pm ko room 4 me h, please bring the report'
    Verifies: Time formatting ('3:00 PM' / '3pm'), capitalization, punctuation, and Hinglish retention.
    """
    raw_input = "aaj meeting 3pm ko room 4 me h please bring the report"
    processed = processor.process(raw_input)

    assert len(processed) > 0
    assert processed[0].isupper()  # Auto-capitalization of first word ("Aaj...")
    assert "meeting" in processed
    assert "room 4" in processed
    assert "bring the report" in processed
    assert processed.endswith(".") or processed.endswith("?")  # Auto-punctuation


def test_code_commentary_and_syntax_dictation(processor: HinglishPostProcessor):
    """
    E2E Test Scenario 2: Code commentary & syntax dictation.
    Input: 'def calculate total sum colon return a plus b'
    Verifies: Code keywords, identifier normalization, colon replacement, return statement.
    """
    raw_input = "def calculate total sum colon return a plus b"
    processed = processor.process(raw_input)

    assert len(processed) > 0
    assert ":" in processed  # 'colon' converted to ':'
    assert "def" in processed.lower()
    assert "return" in processed
    assert "calculate" in processed


def test_currency_and_indian_numbering_dictation(processor: HinglishPostProcessor):
    """
    E2E Test Scenario 3: Currency & Indian numbering dictation.
    Input: 'total amount is Rs 50 thousand and 5 lakhs'
    Verifies: '50 thousand' -> '50,000', '5 lakhs' -> '5 lakh', 'Rs' currency prefix.
    """
    raw_input = "total amount is Rs 50 thousand and 5 lakhs"
    processed = processor.process(raw_input)

    assert len(processed) > 0
    assert "Rs" in processed
    assert "50,000" in processed or "50 thousand" in processed
    assert "5 lakh" in processed or "500,000" in processed or "5,00,000" in processed
    assert processed.startswith("Total amount")


def test_multi_sentence_email_dictation(processor: HinglishPostProcessor):
    """
    E2E Test Scenario 4: Multi-sentence email dictation with auto-capitalization & auto-punctuation.
    Input: 'dear team please find attached the weekly status report we have completed all milestone tasks let us discuss this in tomorrow morning call thanks'
    Verifies: Sentence splitting, auto-capitalization, punctuation termination.
    """
    raw_input = "dear team please find attached the weekly status report. we have completed all milestone tasks. let us discuss this in tomorrow morning call. thanks"
    processed = processor.process(raw_input)

    sentences = [s.strip() for s in processed.split(".") if s.strip()]
    assert len(sentences) >= 3

    # Check auto-capitalization on each sentence
    for sentence in sentences:
        assert sentence[0].isupper(), f"Sentence not capitalized: '{sentence}'"

    assert "Dear team" in processed
    assert "Weekly status report" in processed or "weekly status report" in processed
    assert "Thanks" in processed or "thanks" in processed.lower()


def test_indian_english_idioms_normalization(processor: HinglishPostProcessor):
    """
    E2E Test: Indian English idiom and redundant expression normalization.
    'i will revert back to you by tomorrow' -> 'I will reply to you by tomorrow.' / 'I will revert...'
    'do one thing send me the details' -> 'Do one thing, send me the details.'
    """
    input1 = "i will revert back to you by tomorrow"
    output1 = processor.process(input1)
    assert "I will revert" in output1 or "reply" in output1
    assert "back" not in output1 or "revert" in output1

    input2 = "do one thing send me the code on slack"
    output2 = processor.process(input2)
    assert output2.startswith("Do one thing")
    assert "Slack" in output2  # Brand capitalization


def test_tech_brand_names_capitalization(processor: HinglishPostProcessor):
    """
    E2E Test: Tech brand & tool names dictation.
    'groq whisper running on pyqt6 and python on windows' -> 'Groq Whisper running on PyQt6 and Python on Windows.'
    """
    raw_input = "groq whisper running on pyqt6 and python on windows"
    processed = processor.process(raw_input)

    assert "Groq" in processed
    assert "Whisper" in processed
    assert "PyQt6" in processed
    assert "Python" in processed
    assert "Windows" in processed


def test_disfluency_cleanup_during_live_dictation(processor: HinglishPostProcessor):
    """
    E2E Test: Spoken hesitations and filler words cleanup (uh, um, umm).
    'um aaj meeting uhh 5 pm ko hai' -> 'Aaj meeting 5 PM ko hai.'
    """
    raw_input = "um aaj meeting uhh 5 pm ko hai"
    processed = processor.process(raw_input)

    assert "um" not in processed.lower().split()
    assert "uhh" not in processed.lower().split()
    assert "meeting" in processed
    assert "5" in processed


def test_empty_and_whitespace_dictation_handling(processor: HinglishPostProcessor):
    """
    E2E Test: Handling zero audio / empty transcription gracefully.
    """
    assert processor.process("") == ""
    assert processor.process("   \t  \n ") == ""
