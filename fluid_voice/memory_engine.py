"""
fluid_voice.memory_engine
-------------------------
Contextual Self-Growing Personal Lexicon RAG Engine for FluidVoice.
Manages user memory terms, jargon, brand names, and phonetic mappings with thread-safe
atomic persistence, multi-factor RAG retrieval, token budget capping, and auto-learning.
"""

import difflib
import json
import logging
import math
import os
import re
import time
import uuid
import threading
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from fluid_voice.config import get_app_data_dir
from fluid_voice.post_processor import double_metaphone

logger = logging.getLogger(__name__)


def compute_metaphone_keys(term: str) -> List[str]:
    """Computes unique non-empty primary and secondary Double Metaphone keys for a term."""
    if not term or not term.strip():
        return []
    keys = []
    words = term.strip().split()
    for w in words:
        p, s = double_metaphone(w)
        if p and p not in keys:
            keys.append(p)
        if s and s not in keys:
            keys.append(s)
    return keys


def diff_tokens(spoken_text: str, corrected_text: str) -> List[Tuple[str, str]]:
    """
    Word-level token diffing using difflib.
    Compares spoken_text against corrected_text and isolates
    removed (-) tokens as spoken variants and added (+) tokens as canonical corrections.
    Returns a list of (spoken_variant, canonical_term) tuples.
    """
    if not spoken_text or not corrected_text:
        return []

    spoken_words = spoken_text.strip().split()
    corrected_words = corrected_text.strip().split()

    if not spoken_words or not corrected_words:
        return []

    # Use difflib.Differ and SequenceMatcher for exact token range isolation
    differ = difflib.Differ()
    _ = list(differ.compare(spoken_words, corrected_words))

    matcher = difflib.SequenceMatcher(None, spoken_words, corrected_words, autojunk=False)
    opcodes = matcher.get_opcodes()

    pairs = []
    i = 0
    while i < len(opcodes):
        tag, i1, i2, j1, j2 = opcodes[i]
        if tag == "replace":
            spk = " ".join(spoken_words[i1:i2]).strip(".,!?;:\"'()[]{}")
            cor = " ".join(corrected_words[j1:j2]).strip(".,!?;:\"'()[]{}")
            if spk and cor and spk.lower() != cor.lower():
                pairs.append((spk, cor))
        elif tag == "delete" and i + 1 < len(opcodes) and opcodes[i + 1][0] == "insert":
            _, ni1, ni2, _, _ = opcodes[i]
            _, _, _, nj1, nj2 = opcodes[i + 1]
            spk = " ".join(spoken_words[ni1:ni2]).strip(".,!?;:\"'()[]{}")
            cor = " ".join(corrected_words[nj1:nj2]).strip(".,!?;:\"'()[]{}")
            if spk and cor and spk.lower() != cor.lower():
                pairs.append((spk, cor))
            i += 1
        i += 1

    if not pairs and spoken_text.strip().lower() != corrected_text.strip().lower():
        spk = spoken_text.strip().strip(".,!?;:\"'()[]{}")
        cor = corrected_text.strip().strip(".,!?;:\"'()[]{}")
        if spk and cor and spk.lower() != cor.lower():
            pairs.append((spk, cor))

    return pairs


class MemoryCategory(str, Enum):
    """Categories for user personal lexicon items."""
    JARGON = "JARGON"
    BRAND = "BRAND"
    PHONETIC = "PHONETIC"
    CUSTOM = "CUSTOM"


@dataclass
class MemoryItem:
    """
    Data model for a single lexicon term in personal memory.
    """
    term: str
    category: MemoryCategory | str = MemoryCategory.CUSTOM
    phonetic_variants: List[str] = field(default_factory=list)
    metaphone_keys: List[str] = field(default_factory=list)
    context_tags: List[str] = field(default_factory=list)
    usage_count: int = 0
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    auto_learned: bool = False

    @property
    def last_used_at(self) -> float:
        return self.last_used

    @last_used_at.setter
    def last_used_at(self, value: float) -> None:
        self.last_used = value

    def to_dict(self) -> Dict[str, Any]:
        cat_val = self.category.value if isinstance(self.category, Enum) else str(self.category)
        return {
            "id": self.id,
            "term": self.term,
            "category": cat_val,
            "phonetic_variants": list(self.phonetic_variants),
            "metaphone_keys": list(self.metaphone_keys),
            "context_tags": list(self.context_tags),
            "usage_count": self.usage_count,
            "created_at": self.created_at,
            "last_used": self.last_used,
            "last_used_at": self.last_used,
            "auto_learned": self.auto_learned,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryItem":
        if not isinstance(data, dict) or "term" not in data or not isinstance(data["term"], str):
            raise ValueError("Invalid MemoryItem dict: missing string 'term'")

        cat_val = data.get("category", MemoryCategory.CUSTOM.value)
        try:
            category = MemoryCategory(cat_val)
        except ValueError:
            category = cat_val

        last_used_val = data.get("last_used", data.get("last_used_at", time.time()))

        return cls(
            id=str(data.get("id", str(uuid.uuid4()))),
            term=str(data["term"]),
            category=category,
            phonetic_variants=list(data.get("phonetic_variants", [])),
            metaphone_keys=list(data.get("metaphone_keys", [])),
            context_tags=list(data.get("context_tags", [])),
            usage_count=int(data.get("usage_count", 0)),
            created_at=float(data.get("created_at", time.time())),
            last_used=float(last_used_val),
            auto_learned=bool(data.get("auto_learned", False)),
        )



class MemoryStore:
    """
    Thread-safe, atomic file persistence store for user memory.
    Handles JSON saving/loading, atomic write-replace (.json.tmp),
    corrupted file recovery (.corrupt.<timestamp>), and schema sanitization.
    """

    def __init__(self, filepath: Optional[Path | str] = None):
        if filepath is None:
            self.filepath = get_app_data_dir() / "user_memory.json"
        else:
            self.filepath = Path(filepath)

        self._lock = threading.RLock()
        self._in_memory_only = False
        self.version = "1.0"
        self.last_updated = time.time()
        self.items: Dict[str, MemoryItem] = {}  # id -> MemoryItem
        self.phonetic_mappings: Dict[str, str] = {}  # lowercased variant -> canonical term

        self.load()

    def load(self) -> None:
        """Loads memory store state from disk with corrupted file recovery."""
        with self._lock:
            if not self.filepath.exists():
                self.items = {}
                self.phonetic_mappings = {}
                self.save()
                return

            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if not isinstance(data, dict):
                    raise ValueError("JSON root must be an object")

                self.version = str(data.get("version", "1.0"))
                self.last_updated = float(data.get("last_updated", time.time()))

                # Load terms with schema sanitization
                self.items = {}
                raw_terms = data.get("custom_terms", [])
                if isinstance(raw_terms, list):
                    for raw_item in raw_terms:
                        try:
                            item = MemoryItem.from_dict(raw_item)
                            self.items[item.id] = item
                        except Exception as e:
                            logger.warning(f"Discarding invalid memory term record: {raw_item} (error: {e})")

                # Load phonetic mappings dictionary
                raw_mappings = data.get("phonetic_mappings", {})
                self.phonetic_mappings = {}
                if isinstance(raw_mappings, dict):
                    for k, v in raw_mappings.items():
                        if isinstance(k, str) and isinstance(v, str):
                            self.phonetic_mappings[k.strip().lower()] = v

                # Supplement phonetic_mappings from item phonetic_variants
                for item in self.items.values():
                    for var in item.phonetic_variants:
                        var_lower = var.strip().lower()
                        if var_lower and var_lower not in self.phonetic_mappings:
                            self.phonetic_mappings[var_lower] = item.term

            except (json.JSONDecodeError, UnicodeDecodeError, ValueError, TypeError) as corrupt_err:
                logger.error(f"Corrupted JSON in memory store at {self.filepath}: {corrupt_err}")
                self._backup_corrupt_file()
                self.items = {}
                self.phonetic_mappings = {}
                self.save()
            except PermissionError as perm_err:
                logger.warning(
                    f"Permission denied reading memory store at {self.filepath}: {perm_err}. "
                    "Falling back to clean in-memory defaults."
                )
                self.items = {}
                self.phonetic_mappings = {}
            except Exception as e:
                logger.error(f"Unexpected error loading memory store: {e}")
                self.items = {}
                self.phonetic_mappings = {}

    def _backup_corrupt_file(self) -> None:
        """Creates a timestamped backup of a corrupted user_memory.json file."""
        try:
            if self.filepath.exists():
                timestamp = int(time.time())
                corrupt_path = self.filepath.with_name(f"{self.filepath.name}.corrupt.{timestamp}")
                self.filepath.rename(corrupt_path)
                logger.info(f"Corrupted memory file backed up to {corrupt_path}")
        except Exception as e:
            logger.error(f"Failed to backup corrupt memory file: {e}")

    def save(self) -> bool:
        """Atomically saves memory store state to disk using .json.tmp replacement."""
        with self._lock:
            self.last_updated = time.time()
            data_dict = {
                "version": self.version,
                "last_updated": self.last_updated,
                "phonetic_mappings": self.phonetic_mappings,
                "custom_terms": [item.to_dict() for item in self.items.values()],
            }

            temp_file = self.filepath.with_suffix(".json.tmp")
            try:
                self.filepath.parent.mkdir(parents=True, exist_ok=True)
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(data_dict, f, indent=2, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())

                # Windows transient lock collision retry loop
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        temp_file.replace(self.filepath)
                        break
                    except PermissionError:
                        if attempt == max_retries - 1:
                            raise
                        time.sleep(0.01)

                return True
            except (PermissionError, OSError) as e:
                logger.error(f"Permission or I/O error saving memory store to {self.filepath}: {e}")
                self._in_memory_only = True
                return False
            except Exception as e:
                logger.error(f"Failed to save memory store to {self.filepath}: {e}")
                return False
            finally:
                if temp_file.exists():
                    try:
                        temp_file.unlink()
                    except Exception:
                        pass


class MemoryEngine:
    """
    Context-Aware Self-Growing Personal Lexicon RAG Engine.
    Provides RAG retrieval, top-K token budget capping, phonetic lookup,
    and auto-learning from user corrections.
    """

    def __init__(self, filepath: Optional[Path | str] = None, store: Optional[MemoryStore] = None):
        self._lock = threading.RLock()
        if store is not None:
            self.store = store
        else:
            self.store = MemoryStore(filepath=filepath)

        # Fast lookup indexes
        self._phonetic_lookup: Dict[str, str] = {}
        self._term_lookup: Dict[str, MemoryItem] = {}
        self._tag_index: Dict[str, Set[str]] = {}  # Tag (UPPER) -> Set of Item IDs
        self._rebuild_indexes()

    def _rebuild_indexes(self) -> None:
        """Rebuilds fast lookup indexes for sub-millisecond retrieval."""
        with self._lock:
            self._phonetic_lookup = dict(self.store.phonetic_mappings)
            self._term_lookup = {}
            self._tag_index = {}

            for item in self.store.items.values():
                term_lower = item.term.lower().strip()
                self._term_lookup[term_lower] = item

                for var in item.phonetic_variants:
                    var_lower = var.lower().strip()
                    if var_lower:
                        self._phonetic_lookup[var_lower] = item.term

                for tag in item.context_tags:
                    tag_upper = tag.upper().strip()
                    if tag_upper:
                        if tag_upper not in self._tag_index:
                            self._tag_index[tag_upper] = set()
                        self._tag_index[tag_upper].add(item.id)

    def load(self) -> None:
        """Reloads store from disk and rebuilds indexes."""
        with self._lock:
            self.store.load()
            self._rebuild_indexes()

    def save(self) -> bool:
        """Saves store to disk."""
        with self._lock:
            return self.store.save()

    def add_term(
        self,
        term: str,
        category: MemoryCategory | str = MemoryCategory.CUSTOM,
        phonetic_variants: Optional[List[str]] = None,
        metaphone_keys: Optional[List[str]] = None,
        context_tags: Optional[List[str]] = None,
        usage_count: int = 0,
        auto_learned: bool = False,
    ) -> MemoryItem:
        """Adds a new memory term or updates existing term by canonical name."""
        with self._lock:
            term_clean = term.strip()
            if not term_clean:
                raise ValueError("Term string cannot be empty")

            variants = [v.strip() for v in (phonetic_variants or []) if v.strip()]
            tags = [t.strip() for t in (context_tags or []) if t.strip()]

            computed_metaphones = set(metaphone_keys or [])
            if not computed_metaphones:
                for mk in compute_metaphone_keys(term_clean):
                    computed_metaphones.add(mk)
                for v in variants:
                    for mk in compute_metaphone_keys(v):
                        computed_metaphones.add(mk)

            existing = self._term_lookup.get(term_clean.lower())
            if existing:
                for v in variants:
                    if v not in existing.phonetic_variants:
                        existing.phonetic_variants.append(v)
                for mk in computed_metaphones:
                    if mk not in existing.metaphone_keys:
                        existing.metaphone_keys.append(mk)
                for t in tags:
                    if t not in existing.context_tags:
                        existing.context_tags.append(t)
                existing.usage_count = max(existing.usage_count, usage_count)
                existing.last_used = time.time()
                item = existing
            else:
                item = MemoryItem(
                    term=term_clean,
                    category=category,
                    phonetic_variants=variants,
                    metaphone_keys=list(computed_metaphones),
                    context_tags=tags,
                    usage_count=usage_count,
                    created_at=time.time(),
                    last_used=time.time(),
                    auto_learned=auto_learned,
                )
                self.store.items[item.id] = item

            for v in item.phonetic_variants:
                self.store.phonetic_mappings[v.lower()] = item.term

            self.store.save()
            self._rebuild_indexes()
            return item

    def add_memory(
        self,
        term: str,
        category: MemoryCategory | str = MemoryCategory.CUSTOM,
        phonetic_variants: Optional[List[str]] = None,
        context_tags: Optional[List[str]] = None,
    ) -> MemoryItem:
        """Alias for add_term."""
        return self.add_term(
            term=term,
            category=category,
            phonetic_variants=phonetic_variants,
            context_tags=context_tags,
        )

    def get_term_by_id(self, item_id: str) -> Optional[MemoryItem]:
        """Retrieves a memory item by ID."""
        with self._lock:
            return self.store.items.get(item_id)

    def get_all_terms(self) -> List[MemoryItem]:
        """Returns all memory items."""
        with self._lock:
            return list(self.store.items.values())

    def update_term(self, item_id: str, **kwargs) -> Optional[MemoryItem]:
        """Updates attributes of an existing memory item by ID."""
        with self._lock:
            item = self.store.items.get(item_id)
            if not item:
                return None

            for key, val in kwargs.items():
                if hasattr(item, key):
                    setattr(item, key, val)

            item.last_used = time.time()

            # Update phonetic mappings
            for v in item.phonetic_variants:
                self.store.phonetic_mappings[v.lower()] = item.term

            self.store.save()
            self._rebuild_indexes()
            return item

    def delete_term(self, item_id: str) -> bool:
        """Deletes a memory item by ID."""
        with self._lock:
            if item_id in self.store.items:
                item = self.store.items.pop(item_id)
                # Remove phonetic mappings for this item
                vars_to_remove = [k for k, v in self.store.phonetic_mappings.items() if v == item.term]
                for v in vars_to_remove:
                    self.store.phonetic_mappings.pop(v, None)

                self.store.save()
                self._rebuild_indexes()
                return True
            return False

    def delete_memory(self, item_id: str) -> bool:
        """Alias for delete_term."""
        return self.delete_term(item_id)

    def lookup_phonetic(self, spoken_variant: str) -> Optional[str]:
        """Returns canonical term for a lowercased spoken variant if found."""
        with self._lock:
            if not spoken_variant:
                return None
            return self._phonetic_lookup.get(spoken_variant.strip().lower())

    def get_phonetic_mappings(self) -> Dict[str, str]:
        """Returns a copy of all phonetic mappings (variant -> canonical term)."""
        with self._lock:
            return dict(self._phonetic_lookup)

    def get_relevant_memories(
        self,
        context: Optional[Any] = None,
        raw_text: str = "",
        limit: int = 15,
        max_token_budget: int = 150,
    ) -> List[MemoryItem]:
        """
        Multi-factor RAG retrieval for live dictation.
        Scores and ranks memory items using context matching, exact phonetic/canonical matches,
        frequency boost, and recency decay. Capped by top-K limit and token budget.
        """
        with self._lock:
            all_items = list(self.store.items.values())
            if not all_items:
                return []

            raw_text_clean = raw_text.lower().strip() if raw_text else ""
            raw_tokens = set(re.findall(r"\b\w+\b", raw_text_clean)) if raw_text_clean else set()

            # Extract context tags
            ctx_tags: Set[str] = set()
            if context is not None:
                app_cat = getattr(context, "app_category", None)
                if app_cat is not None:
                    cat_str = app_cat.value if hasattr(app_cat, "value") else str(app_cat)
                    ctx_tags.add(cat_str.upper())

                for attr in ["browser_domain", "exe_name", "window_title"]:
                    val = getattr(context, attr, None)
                    if val:
                        ctx_tags.add(str(val).upper())

            # Fast candidate selection
            if len(all_items) <= 100:
                candidates = all_items
            else:
                candidate_ids: Set[str] = set()
                # 1. Tag matches
                for tag in ctx_tags:
                    if tag in self._tag_index:
                        candidate_ids.update(self._tag_index[tag])

                # 2. Text matches (exact token and n-gram hashtable lookups)
                for tok in raw_tokens:
                    if tok in self._phonetic_lookup:
                        term_name = self._phonetic_lookup[tok]
                        if term_name.lower() in self._term_lookup:
                            candidate_ids.add(self._term_lookup[term_name.lower()].id)
                    if tok in self._term_lookup:
                        candidate_ids.add(self._term_lookup[tok].id)

                # Generate 2-gram and 3-gram candidate tokens
                if len(raw_tokens) >= 2:
                    for i in range(len(raw_tokens) - 1):
                        bigram = f"{raw_tokens[i]} {raw_tokens[i+1]}"
                        if bigram in self._phonetic_lookup:
                            term_name = self._phonetic_lookup[bigram]
                            if term_name.lower() in self._term_lookup:
                                candidate_ids.add(self._term_lookup[term_name.lower()].id)
                        if bigram in self._term_lookup:
                            candidate_ids.add(self._term_lookup[bigram].id)

                if len(raw_tokens) >= 3:
                    for i in range(len(raw_tokens) - 2):
                        trigram = f"{raw_tokens[i]} {raw_tokens[i+1]} {raw_tokens[i+2]}"
                        if trigram in self._phonetic_lookup:
                            term_name = self._phonetic_lookup[trigram]
                            if term_name.lower() in self._term_lookup:
                                candidate_ids.add(self._term_lookup[term_name.lower()].id)
                        if trigram in self._term_lookup:
                            candidate_ids.add(self._term_lookup[trigram].id)

                # 3. Fallback: if candidates small, include general / recent terms
                if len(candidate_ids) < limit:
                    recent_items = sorted(
                        all_items, key=lambda x: (x.usage_count, x.last_used), reverse=True
                    )[:50]
                    for r_item in recent_items:
                        candidate_ids.add(r_item.id)

                candidates = [self.store.items[cid] for cid in candidate_ids if cid in self.store.items]

            # Score candidates
            now = time.time()
            scored_candidates: List[Tuple[float, MemoryItem]] = []

            for item in candidates:
                score = 0.0
                term_lower = item.term.lower()

                # Phonetic variant match
                for var in item.phonetic_variants:
                    var_lower = var.lower().strip()
                    if var_lower and raw_text_clean and var_lower in raw_text_clean:
                        score += 10.0
                        break

                # Canonical term match
                if raw_text_clean and term_lower in raw_text_clean:
                    score += 8.0

                # Fuzzy match if no direct match and text provided
                if score == 0.0 and raw_tokens and len(candidates) <= 100:
                    for var in [item.term] + item.phonetic_variants:
                        v_low = var.lower().strip()
                        for tok in raw_tokens:
                            if abs(len(v_low) - len(tok)) <= 2:
                                import difflib
                                if difflib.SequenceMatcher(None, v_low, tok).ratio() >= 0.82:
                                    score += 5.0
                                    break
                        if score > 0:
                            break

                # Context tag match
                item_tags_upper = {t.upper() for t in item.context_tags}
                if ctx_tags and (item_tags_upper & ctx_tags):
                    score += 3.0

                # Frequency boost
                score += min(2.0, math.log2(1 + item.usage_count) * 0.5)

                # Recency boost
                age_sec = max(0.0, now - item.last_used)
                if age_sec < 3600:
                    score += 1.5
                elif age_sec < 86400:
                    score += 1.0
                elif age_sec < 604800:
                    score += 0.5

                if score > 0.0 or not raw_text_clean:
                    scored_candidates.append((score, item))

            # Rank candidates
            scored_candidates.sort(key=lambda x: (x[0], x[1].last_used, x[1].usage_count), reverse=True)

            # Cap by top-K limit and token budget
            results: List[MemoryItem] = []
            current_tokens = 0

            for score, item in scored_candidates:
                if len(results) >= limit:
                    break

                # Estimate tokens for term + variants (~ 1 token per word)
                item_tokens = max(1, len(item.term.split()) + sum(len(v.split()) for v in item.phonetic_variants))

                if current_tokens + item_tokens > max_token_budget and len(results) > 0:
                    break

                results.append(item)
                current_tokens += item_tokens

            return results

    def learn_from_correction(
        self,
        spoken_text: str,
        corrected_term: str,
        context: Optional[Any] = None,
    ) -> Optional[MemoryItem]:
        """
        Auto-learning mechanism using word-level difflib.Differ token diffing.
        Computes primary and secondary Double Metaphone keys and persists to user_memory.json.
        """
        with self._lock:
            spoken_clean = spoken_text.strip()
            corrected_clean = corrected_term.strip()

            if not spoken_clean or not corrected_clean:
                return None

            pairs = diff_tokens(spoken_clean, corrected_clean)
            if not pairs:
                if spoken_clean.lower() != corrected_clean.lower():
                    pairs = [(spoken_clean, corrected_clean)]
                else:
                    pairs = [(corrected_clean, corrected_clean)]

            last_item = None
            for spoken_variant, canonical in pairs:
                can_clean = canonical.strip()
                var_clean = spoken_variant.strip()
                if not can_clean:
                    continue

                var_lower = var_clean.lower()
                can_lower = can_clean.lower()

                existing = self._term_lookup.get(can_lower)

                meta_keys = set()
                for mk in compute_metaphone_keys(can_clean):
                    meta_keys.add(mk)
                if var_clean and var_lower != can_lower:
                    for mk in compute_metaphone_keys(var_clean):
                        meta_keys.add(mk)

                if existing:
                    if var_lower != can_lower and var_clean not in existing.phonetic_variants:
                        existing.phonetic_variants.append(var_clean)
                    for mk in meta_keys:
                        if mk not in existing.metaphone_keys:
                            existing.metaphone_keys.append(mk)
                    existing.usage_count += 1
                    existing.last_used = time.time()
                    existing.auto_learned = True

                    if context is not None:
                        app_cat = getattr(context, "app_category", None)
                        if app_cat is not None:
                            cat_str = app_cat.value if hasattr(app_cat, "value") else str(app_cat)
                            if cat_str not in existing.context_tags:
                                existing.context_tags.append(cat_str)

                    item = existing
                else:
                    variants = [var_clean] if var_lower != can_lower else []
                    tags = []
                    if context is not None:
                        app_cat = getattr(context, "app_category", None)
                        if app_cat is not None:
                            cat_str = app_cat.value if hasattr(app_cat, "value") else str(app_cat)
                            tags.append(cat_str)

                    item = MemoryItem(
                        term=can_clean,
                        category=MemoryCategory.JARGON,
                        phonetic_variants=variants,
                        metaphone_keys=list(meta_keys),
                        context_tags=tags,
                        usage_count=1,
                        created_at=time.time(),
                        last_used=time.time(),
                        auto_learned=True,
                    )
                    self.store.items[item.id] = item

                for v in item.phonetic_variants:
                    self.store.phonetic_mappings[v.lower()] = item.term

                last_item = item

            self.store.save()
            self._rebuild_indexes()
            return last_item

    def build_stt_vocab_prompt(
        self,
        context: Optional[Any] = None,
        raw_text: str = "",
        limit: int = 15,
    ) -> str:
        """
        Generates vocabulary prompt string for pre-conditioning Whisper ASR engine.
        Capped to limit terms (~40 tokens).
        """
        memories = self.get_relevant_memories(
            context=context,
            raw_text=raw_text,
            limit=limit,
            max_token_budget=60,
        )
        if not memories:
            return ""

        terms = [m.term for m in memories]
        return f"Lexicon: {', '.join(terms)}."
