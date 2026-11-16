"""
RAG grounding assertions.

A Retrieval-Augmented Generation answer is *grounded* if every factual
claim it makes can be traced back to one of the retrieved chunks. Bugs
this catches:

* Model cites chunk IDs that weren't actually retrieved.
* Model returns text not present in *any* retrieved chunk (pure
  hallucination).
* Citation density too low (< X cites per N words).
* Chunk overlap with answer too low (< Y% lexical overlap).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class RagGroundingError(WebRunnerException):
    """Raised when a RAG output is insufficiently grounded."""


@dataclass
class Chunk:
    """A retrieved passage and the id it is cited by; the id must not be empty."""
    chunk_id: str
    text: str

    def __post_init__(self) -> None:
        if not self.chunk_id:
            raise RagGroundingError("chunk_id required")


@dataclass
class RagAnswer:
    """The generated answer text and the ids of the chunks it cites."""
    text: str
    cited_chunk_ids: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.text, str):
            raise RagGroundingError("text must be string")


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in re.findall(r"\w{3,}", text or "")}


def assert_citations_in_retrieved(
    answer: RagAnswer, retrieved: Sequence[Chunk],
) -> None:
    """Every cited chunk_id must appear in the retrieved set."""
    available = {c.chunk_id for c in retrieved}
    invalid = [c for c in answer.cited_chunk_ids if c not in available]
    if invalid:
        raise RagGroundingError(
            f"answer cites unretrieved chunk(s): {invalid}"
        )


def assert_min_citations(answer: RagAnswer, *, minimum: int) -> None:
    """Raise RagGroundingError when the answer cites fewer than ``minimum`` chunks."""
    if minimum < 1:
        raise RagGroundingError("minimum must be >= 1")
    if len(answer.cited_chunk_ids) < minimum:
        raise RagGroundingError(
            f"answer has only {len(answer.cited_chunk_ids)} citations, "
            f"required >= {minimum}"
        )


def lexical_overlap_score(
    answer: RagAnswer, retrieved: Sequence[Chunk],
) -> float:
    """Fraction of answer tokens present in any retrieved chunk."""
    answer_tokens = _tokens(answer.text)
    if not answer_tokens:
        return 0.0
    retrieved_tokens: set[str] = set()
    for c in retrieved:
        retrieved_tokens |= _tokens(c.text)
    return len(answer_tokens & retrieved_tokens) / len(answer_tokens)


def assert_grounded(
    answer: RagAnswer,
    retrieved: Sequence[Chunk],
    *,
    min_overlap: float = 0.5,
) -> None:
    """Raise RagGroundingError when the lexical overlap between the answer and the retrieved
    chunks is below ``min_overlap`` (which must be within [0, 1]).
    """
    if not 0 <= min_overlap <= 1:
        raise RagGroundingError("min_overlap must be in [0, 1]")
    score = lexical_overlap_score(answer, retrieved)
    if score < min_overlap:
        raise RagGroundingError(
            f"answer-retrieved lexical overlap {score:.2f} < {min_overlap}"
        )


def find_unsupported_claims(
    answer: RagAnswer,
    retrieved: Sequence[Chunk],
    *,
    min_phrase_len: int = 4,
) -> list[str]:
    """Return ``n``-token phrases in the answer that don't appear in any chunk."""
    if min_phrase_len < 2:
        raise RagGroundingError("min_phrase_len must be >= 2")
    answer_words = re.findall(r"\w+", answer.text)
    if len(answer_words) < min_phrase_len:
        return []
    haystack = " ".join((c.text or "").lower() for c in retrieved)
    unsupported: list[str] = []
    for i in range(len(answer_words) - min_phrase_len + 1):
        phrase = " ".join(answer_words[i:i + min_phrase_len]).lower()
        if phrase not in haystack:
            unsupported.append(phrase)
    return unsupported


def assert_no_hallucination(
    answer: RagAnswer,
    retrieved: Sequence[Chunk],
    *,
    max_unsupported_phrases: int = 0,
    min_phrase_len: int = 4,
) -> None:
    """Raise RagGroundingError when the answer has more than ``max_unsupported_phrases`` word
    sequences of length ``min_phrase_len`` that no retrieved chunk supports.
    """
    unsupported = find_unsupported_claims(
        answer, retrieved, min_phrase_len=min_phrase_len,
    )
    if len(unsupported) > max_unsupported_phrases:
        raise RagGroundingError(
            f"answer has {len(unsupported)} unsupported "
            f"{min_phrase_len}-grams (limit {max_unsupported_phrases}): "
            f"e.g. {unsupported[:3]}"
        )
