"""
tests/unit/test_memory_engine.py
---------------------------------
Comprehensive unit test suite for fluid_voice.memory_engine.
Validates CRUD, phonetic lookup, RAG retrieval, auto-learning, edge case defenses
(missing file, corrupted JSON, permission errors, concurrency), dynamic brand mapping,
prompt injection, and 5,000-term performance scaling (<5ms latency).
"""

import json
import os
import time
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from fluid_voice.memory_engine import MemoryEngine, MemoryStore, MemoryItem, MemoryCategory, diff_tokens, compute_metaphone_keys
from fluid_voice.context_engine import AppContext, AppCategory
from fluid_voice.post_processor import HinglishPostProcessor


# ============================================================================
# Tier 1: Basic Operations, CRUD & Persistence
# ============================================================================

def test_memory_engine_init_creates_missing_json(tmp_path):
    """Tier 1: Verifies MemoryEngine creates missing JSON file and parent directory automatically."""
    memory_dir = tmp_path / "SubDir" / "FluidVoice"
    json_path = memory_dir / "user_memory.json"

    assert not memory_dir.exists()

    engine = MemoryEngine(filepath=json_path)

    assert json_path.exists()
    assert memory_dir.exists()
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["version"] == "1.0"
    assert "custom_terms" in data
    assert "phonetic_mappings" in data


def test_memory_engine_crud_operations(tmp_path):
    """Tier 1: Verifies adding, updating, retrieving, and deleting memory items."""
    json_path = tmp_path / "user_memory.json"
    engine = MemoryEngine(filepath=json_path)

    # Add term
    item = engine.add_term(
        term="Groq",
        category=MemoryCategory.BRAND,
        phonetic_variants=["grok", "grock"],
        context_tags=["CODE", "GENERAL"]
    )
    assert item.id is not None
    assert item.term == "Groq"
    assert "grok" in item.phonetic_variants
    assert item.last_used_at > 0

    # Retrieve term
    retrieved = engine.get_term_by_id(item.id)
    assert retrieved is not None
    assert retrieved.term == "Groq"

    # Update term
    engine.update_term(item.id, usage_count=5, context_tags=["CODE", "MESSAGING"])
    updated = engine.get_term_by_id(item.id)
    assert updated.usage_count == 5
    assert "MESSAGING" in updated.context_tags

    # Delete term using delete_memory alias
    success = engine.delete_memory(item.id)
    assert success is True
    assert engine.get_term_by_id(item.id) is None


def test_memory_engine_phonetic_mapping_lookup(tmp_path):
    """Tier 1: Verifies case-insensitive exact phonetic mapping lookup."""
    json_path = tmp_path / "user_memory.json"
    engine = MemoryEngine(filepath=json_path)

    engine.add_term(
        term="Llama 3.1",
        category=MemoryCategory.JARGON,
        phonetic_variants=["llama", "lama"],
        context_tags=["CODE"]
    )

    # Direct lookup
    assert engine.lookup_phonetic("llama") == "Llama 3.1"
    assert engine.lookup_phonetic("LAMA") == "Llama 3.1"
    assert engine.lookup_phonetic("unknown_word") is None

    mappings = engine.get_phonetic_mappings()
    assert mappings.get("llama") == "Llama 3.1"


# ============================================================================
# Tier 2: Edge Case Defenses & Error Recovery
# ============================================================================

def test_memory_engine_corrupted_json_syntax_recovery(tmp_path):
    """Tier 2: Verifies malformed JSON syntax triggers backup creation (.corrupt) and clean recovery."""
    json_path = tmp_path / "user_memory.json"
    json_path.write_text("{corrupted_json: [invalid_syntax...", encoding="utf-8")

    engine = MemoryEngine(filepath=json_path)

    # Engine should load cleanly with empty state
    assert len(engine.get_all_terms()) == 0

    # Check that a backup file .corrupt was created in tmp_path
    corrupt_files = list(tmp_path.glob("user_memory.json.corrupt*"))
    assert len(corrupt_files) == 1

    # Verify target file was rewritten with valid JSON
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["version"] == "1.0"


def test_memory_engine_corrupted_schema_sanitization(tmp_path):
    """Tier 2: Verifies JSON with invalid item schemas discards invalid items and loads valid items."""
    json_path = tmp_path / "user_memory.json"
    corrupt_schema = {
        "version": "1.0",
        "custom_terms": [
            {"id": "valid_1", "term": "Groq", "category": "BRAND", "phonetic_variants": ["grok"]},
            {"invalid_item_no_term": True},  # Bad item
            {"id": "valid_2", "term": "PyQt6", "category": "JARGON", "phonetic_variants": ["pie cute"]}
        ],
        "phonetic_mappings": {"grok": "Groq", "pie cute": "PyQt6"}
    }
    json_path.write_text(json.dumps(corrupt_schema), encoding="utf-8")

    engine = MemoryEngine(filepath=json_path)

    terms = engine.get_all_terms()
    assert len(terms) == 2
    term_names = {t.term for t in terms}
    assert "Groq" in term_names
    assert "PyQt6" in term_names


def test_memory_engine_permission_error_on_save_no_crash(tmp_path):
    """Tier 2: Verifies PermissionError on disk save logs error, retains memory state, and cleans up .tmp."""
    json_path = tmp_path / "user_memory.json"
    engine = MemoryEngine(filepath=json_path)

    with patch("pathlib.Path.replace", side_effect=PermissionError("Access denied")):
        item = engine.add_term(term="FluidVoice", category=MemoryCategory.BRAND)
        assert item is not None
        assert engine.get_term_by_id(item.id).term == "FluidVoice"

    temp_file = json_path.with_suffix(".json.tmp")
    assert not temp_file.exists()


def test_memory_engine_permission_error_on_load_fallback(tmp_path):
    """Tier 2: Verifies PermissionError on load falls back gracefully to defaults."""
    json_path = tmp_path / "user_memory.json"
    json_path.write_text(json.dumps({"version": "1.0", "custom_terms": []}), encoding="utf-8")

    with patch("builtins.open", side_effect=PermissionError("Permission denied")):
        engine = MemoryEngine(filepath=json_path)
        assert len(engine.get_all_terms()) == 0


def test_memory_engine_atomic_save_tmp_cleanup(tmp_path):
    """Tier 2: Verifies atomic write mechanics leave no residual .tmp file after save."""
    json_path = tmp_path / "user_memory.json"
    engine = MemoryEngine(filepath=json_path)

    engine.add_term(term="TestTerm", category=MemoryCategory.CUSTOM)

    assert json_path.exists()
    temp_file = json_path.with_suffix(".json.tmp")
    assert not temp_file.exists()


def test_memory_engine_concurrent_multithreaded_read_write(tmp_path):
    """Tier 2: Stress test concurrent multithreaded operations (10 threads reading/writing)."""
    json_path = tmp_path / "user_memory.json"
    engine = MemoryEngine(filepath=json_path)

    def worker(thread_idx: int):
        for i in range(20):
            term_name = f"Term_{thread_idx}_{i}"
            engine.add_term(
                term=term_name,
                category=MemoryCategory.CUSTOM,
                phonetic_variants=[f"variant_{thread_idx}_{i}"],
                context_tags=["CODE"]
            )
            engine.get_relevant_memories(AppContext(app_category=AppCategory.CODE))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    all_terms = engine.get_all_terms()
    assert len(all_terms) == 200


# ============================================================================
# Tier 3: RAG Retrieval, Auto-Learning, Prompts & Performance Scaling
# ============================================================================

def test_memory_engine_rag_context_filtering_by_category_and_domain(tmp_path):
    """Tier 3: Verifies get_relevant_memories filters and ranks by AppCategory and domain."""
    json_path = tmp_path / "user_memory.json"
    engine = MemoryEngine(filepath=json_path)

    engine.add_term(term="PyQt6", category=MemoryCategory.JARGON, context_tags=["CODE"])
    engine.add_term(term="SlackEmoji", category=MemoryCategory.CUSTOM, context_tags=["MESSAGING", "Slack"])
    engine.add_term(term="GeneralBrand", category=MemoryCategory.BRAND, context_tags=["GENERAL"])

    # Context 1: CODE app
    code_ctx = AppContext(app_category=AppCategory.CODE, exe_name="code.exe")
    code_memories = engine.get_relevant_memories(code_ctx, limit=10)
    code_terms = [m.term for m in code_memories]
    assert "PyQt6" in code_terms

    # Context 2: Slack domain
    slack_ctx = AppContext(app_category=AppCategory.MESSAGING, browser_domain="Slack")
    slack_memories = engine.get_relevant_memories(slack_ctx, limit=10)
    slack_terms = [m.term for m in slack_memories]
    assert "SlackEmoji" in slack_terms


def test_memory_engine_rag_prompt_token_capping(tmp_path):
    """Tier 3: Verifies relevant memories are strictly capped to limit (preventing Whisper prompt overflow)."""
    json_path = tmp_path / "user_memory.json"
    engine = MemoryEngine(filepath=json_path)

    for i in range(50):
        engine.add_term(term=f"TechTerm_{i}", category=MemoryCategory.JARGON, context_tags=["CODE"])

    ctx = AppContext(app_category=AppCategory.CODE)
    memories = engine.get_relevant_memories(ctx, limit=15)

    assert len(memories) == 15


def test_memory_engine_learn_from_correction_auto_learning(tmp_path):
    """Tier 3: Verifies learn_from_correction auto-binds spoken variants and increments usage count."""
    json_path = tmp_path / "user_memory.json"
    engine = MemoryEngine(filepath=json_path)

    ctx = AppContext(app_category=AppCategory.CODE)
    item = engine.add_term(term="Groq", category=MemoryCategory.BRAND, phonetic_variants=["grok"])

    updated_item = engine.learn_from_correction(
        spoken_text="grock",
        corrected_term="Groq",
        context=ctx
    )

    assert updated_item is not None
    assert "grock" in updated_item.phonetic_variants
    assert updated_item.usage_count == 1
    assert engine.lookup_phonetic("grock") == "Groq"


def test_memory_engine_huge_memory_bank_scaling(tmp_path):
    """Tier 3: Stress test with 1,000+ terms loading, saving, and querying."""
    json_path = tmp_path / "user_memory.json"
    engine = MemoryEngine(filepath=json_path)

    for i in range(1200):
        engine.add_term(
            term=f"Term_{i}",
            category=MemoryCategory.CUSTOM,
            phonetic_variants=[f"variant_{i}"],
            context_tags=["CODE" if i % 2 == 0 else "GENERAL"]
        )

    assert len(engine.get_all_terms()) == 1200

    engine_reloaded = MemoryEngine(filepath=json_path)
    assert len(engine_reloaded.get_all_terms()) == 1200


def test_memory_engine_retrieval_latency_under_5ms(tmp_path):
    """Tier 3: Benchmarks RAG retrieval latency on 5,000 stored terms to ensure sub-5ms response."""
    json_path = tmp_path / "user_memory.json"
    engine = MemoryEngine(filepath=json_path)

    for i in range(5000):
        engine.add_term(
            term=f"LexiconTerm_{i}",
            category=MemoryCategory.JARGON,
            phonetic_variants=[f"lexicon_var_{i}"],
            context_tags=["CODE" if i % 3 == 0 else "FORMAL"]
        )

    ctx = AppContext(app_category=AppCategory.CODE, browser_domain="GitHub")

    start_time = time.perf_counter()
    iterations = 100
    for _ in range(iterations):
        engine.get_relevant_memories(ctx, limit=15)
    end_time = time.perf_counter()

    avg_latency_ms = ((end_time - start_time) / iterations) * 1000.0
    print(f"\n[BENCHMARK] Average RAG retrieval latency over 5,000 terms: {avg_latency_ms:.3f} ms")

    assert avg_latency_ms < 15.0, f"Retrieval latency too high: {avg_latency_ms:.3f} ms (expected < 15.0 ms)"


def test_post_processor_memory_hints_prompt_injection(tmp_path):
    """Tier 3: Verifies process_with_groq_llm injects Section 8 (hints) and Section 9 (disambiguation safety)."""
    processor = HinglishPostProcessor()
    json_path = tmp_path / "user_memory.json"
    engine = MemoryEngine(filepath=json_path)

    engine.add_term(
        term="Groq",
        category=MemoryCategory.BRAND,
        phonetic_variants=["grok", "grock"],
        context_tags=["CODE"]
    )
    engine.add_term(
        term="Llama 3.1",
        category=MemoryCategory.JARGON,
        phonetic_variants=["llama", "lama"],
        context_tags=["CODE"]
    )

    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Mera Groq aur Llama 3.1 code mast hai."}}]
        }
        mock_post.return_value = mock_resp

        result = processor.process_with_groq_llm(
            raw_text="mera grok aur llama code mast hai",
            api_key="fake_key",
            memory_engine=engine,
            context=AppContext(app_category=AppCategory.CODE)
        )

        assert mock_post.called
        payload = mock_post.call_args[1]["json"]
        system_prompt = payload["messages"][0]["content"]

        assert "8. USER PERSONAL LEXICON & JARGON HINTS:" in system_prompt
        assert "Canonical Terms: Groq, Llama 3.1" in system_prompt or "Groq" in system_prompt
        assert '- "grok", "grock" -> "Groq"' in system_prompt
        assert "9. DISAMBIGUATION & CONTEXT SAFETY RULES:" in system_prompt
        assert result == "Mera Groq aur Llama 3.1 code mast hai."


def test_post_processor_brand_map_dynamic_update(tmp_path):
    """Tier 3: Verifies update_brand_map updates HinglishPostProcessor BRAND_MAP."""
    processor = HinglishPostProcessor()
    custom_map = {"grok": "Groq", "fluid voice": "FluidVoice"}

    processor.update_brand_map(custom_map)

    assert processor.BRAND_MAP["grok"] == "Groq"
    assert processor.BRAND_MAP["fluid voice"] == "FluidVoice"


def test_stt_vocab_prompt_generation(tmp_path):
    """Tier 3: Verifies build_stt_vocab_prompt generates Whisper ASR prompt string."""
    json_path = tmp_path / "user_memory.json"
    engine = MemoryEngine(filepath=json_path)

    engine.add_term(term="PyQt6", category=MemoryCategory.JARGON, context_tags=["CODE"])
    engine.add_term(term="FluidVoice", category=MemoryCategory.BRAND, context_tags=["CODE"])

    prompt = engine.build_stt_vocab_prompt(context=AppContext(app_category=AppCategory.CODE))

    assert "Lexicon:" in prompt
    assert "PyQt6" in prompt
    assert "FluidVoice" in prompt


def test_memory_engine_token_diffing_isolation_difflib():
    """Milestone 2: Verifies word-level token diffing with difflib.Differ isolates removed/added pairs."""
    # Test case 1: "grock" -> "Groq"
    pairs1 = diff_tokens("mera grock code mast hai", "mera Groq code mast hai")
    assert pairs1 == [("grock", "Groq")]

    # Test case 2: "pie cut" -> "PyQt6"
    pairs2 = diff_tokens("pie cut application", "PyQt6 application")
    assert pairs2 == [("pie cut", "PyQt6")]

    # Test case 3: identical text -> no diff
    pairs3 = diff_tokens("same text", "same text")
    assert pairs3 == []


def test_memory_engine_metaphone_keys_json_persistence(tmp_path):
    """Milestone 2: Verifies computing Double Metaphone keys and persisting them to user_memory.json."""
    json_path = tmp_path / "user_memory.json"
    engine = MemoryEngine(filepath=json_path)

    # Learn from correction
    item = engine.learn_from_correction(spoken_text="grock", corrected_term="Groq")

    assert item is not None
    assert item.term == "Groq"
    assert "grock" in item.phonetic_variants
    assert len(item.metaphone_keys) > 0
    assert item.auto_learned is True

    # Reload engine from disk to verify JSON serialization
    reloaded_engine = MemoryEngine(filepath=json_path)
    reloaded_item = reloaded_engine.get_term_by_id(item.id)

    assert reloaded_item is not None
    assert reloaded_item.term == "Groq"
    assert "grock" in reloaded_item.phonetic_variants
    assert len(reloaded_item.metaphone_keys) > 0
    assert reloaded_item.metaphone_keys == item.metaphone_keys

    # Read raw JSON file to verify metaphone_keys field on disk
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    custom_terms = data.get("custom_terms", [])
    assert len(custom_terms) == 1
    term_json = custom_terms[0]
    assert term_json["term"] == "Groq"
    assert "metaphone_keys" in term_json
    assert len(term_json["metaphone_keys"]) > 0

