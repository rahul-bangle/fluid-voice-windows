"""
Tier 1 Tests for fluid_voice.post_processor (Hinglish Post-Processor).

Covers happy path feature verification for all 6 passes, zero-dependency assertion,
and sub-5ms performance latency budget.
"""

import time
import pytest
import sys
from fluid_voice.post_processor import HinglishPostProcessor


@pytest.fixture
def processor() -> HinglishPostProcessor:
    return HinglishPostProcessor()


def test_tier1_pass1_whitespace_disfluency(processor: HinglishPostProcessor):
    """Tier 1 Pass 1: Whitespace, filler words ('uh', 'um'), and stutter removal."""
    raw = "uhh hello umm world  the the   system is working"
    result = processor.process(raw)
    assert result == "Hello world the system is working."


def test_tier1_pass2_voice_commands_and_idioms(processor: HinglishPostProcessor):
    """Tier 1 Pass 2: Dictation formatting commands and Indian English idioms."""
    raw = "please do one thing revert back to me comma open bracket urgent close bracket full stop"
    result = processor.process(raw)
    assert "Please do one thing," in result
    assert "revert to me" in result
    assert "(urgent)" in result or "( urgent )" in result or "(urgent)." in result
    assert result.endswith(".")


def test_tier1_pass3_brand_formatting_and_hinglish(processor: HinglishPostProcessor):
    """Tier 1 Pass 3: Tech brands, Indian ecosystem brands, and Hinglish vocabulary."""
    raw = "bhai haa accha groq whisper pyqt vscode paytm upi in bengaluru"
    result = processor.process(raw)
    assert "Groq" in result
    assert "Whisper" in result
    assert "PyQt6" in result
    assert "VS Code" in result
    assert "Paytm" in result
    assert "UPI" in result
    assert "Bengaluru" in result
    assert "haan" in result or "Haan" in result
    assert "accha" in result or "Accha" in result


def test_tier1_pass4_numbers_currency_dates(processor: HinglishPostProcessor):
    """Tier 1 Pass 4: Indian number system (hybrid/digits), currency (Rs/₹), percentages, dates and times."""
    # Hybrid mode
    raw_hybrid = "revenue reached dus lakh rupees on 23rd july at 5 pm with 18 percent growth"
    res_hybrid = processor.process(raw_hybrid)
    assert "10 lakh" in res_hybrid or "Rs 10 lakh" in res_hybrid or "Rs 10,00,000" in res_hybrid
    assert "23rd July" in res_hybrid
    assert "5:00 PM" in res_hybrid
    assert "18%" in res_hybrid

    # Digits mode
    processor_digits = HinglishPostProcessor(config={"indian_number_style": "digits"})
    raw_digits = "total cost 5 lakhs rupees"
    res_digits = processor_digits.process(raw_digits)
    assert "5,00,000" in res_digits or "Rs 5,00,000" in res_digits


def test_tier1_pass5_list_auto_formatting(processor: HinglishPostProcessor):
    """Tier 1 Pass 5: Formatting of spoken list indicators (firstly/secondly, bullets, numbered points)."""
    raw = "firstly submit report secondly review code"
    result = processor.process(raw)
    assert "1. Submit report" in result
    assert "2. Review code" in result


def test_tier1_pass6_punctuation_capitalization(processor: HinglishPostProcessor):
    """Tier 1 Pass 6: Hindi/English question detection and sentence capitalization."""
    # English question starter
    assert processor.process("can you send the file") == "Can you send the file?"
    
    # Hindi question word
    assert processor.process("aapka naam kya hai") == "Aapka naam kya hai?"
    
    # Declarative sentence
    assert processor.process("i am working on python code") == "I am working on Python code."


def test_tier1_zero_external_dependencies():
    """Tier 1 Contract: Verify HinglishPostProcessor source code relies exclusively on standard library modules."""
    import ast
    import inspect
    import fluid_voice.post_processor as mod

    forbidden_modules = {"spacy", "transformers", "torch", "stanza", "nltk", "numpy", "pandas"}
    
    source = inspect.getsource(mod)
    tree = ast.parse(source)
    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_names.add(node.module.split(".")[0])

    for forbidden in forbidden_modules:
        assert forbidden not in imported_names, f"Forbidden heavy library '{forbidden}' imported in post_processor.py!"



def test_tier1_sub_5ms_performance_budget(processor: HinglishPostProcessor):
    """Tier 1 Performance Budget: Single dictation chunk processing time must be < 5ms."""
    raw_dictation = (
        "hello bhai do one thing revert back regarding groq whisper api setup. "
        "the cost is 50 thousand rupees and deadline is 23rd july at 5 pm."
    )
    
    # Warm up regex cache
    processor.process(raw_dictation)
    
    # Measure execution time across 50 iterations
    start_time = time.perf_counter()
    iterations = 50
    for _ in range(iterations):
        processor.process(raw_dictation)
    avg_latency_ms = ((time.perf_counter() - start_time) / iterations) * 1000.0
    
    assert avg_latency_ms < 5.0, f"Average post-processor latency {avg_latency_ms:.2f}ms exceeded 5.0ms budget!"
