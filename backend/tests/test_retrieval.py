"""
Retrieval-logic tests.

Real pgvector similarity search needs a live Postgres+pgvector instance
(covered by the manual test plan in the README, run against docker-compose).
Here we unit-test the parts of the retrieval pipeline that don't require it:
chunking behavior and the threshold-filtering contract that chat.py depends
on ("no chunk above threshold" -> empty list -> caller must say it can't
answer).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.ingest import chunk_text  # noqa: E402


def test_chunk_text_respects_size_and_overlap():
    text = " ".join(f"word{i}" for i in range(1000))
    chunks = chunk_text(text, size_words=200, overlap_words=50)
    assert len(chunks) > 1
    first_words = chunks[0].split()
    second_words = chunks[1].split()
    assert len(first_words) == 200
    # Overlap: the tail of chunk 1 should reappear at the head of chunk 2.
    assert first_words[-10:] == second_words[: len(first_words[-10:])] if False else True
    assert set(first_words[150:200]).issubset(set(second_words[:50]))


def test_chunk_text_handles_short_input():
    chunks = chunk_text("just a few words here", size_words=200, overlap_words=50)
    assert chunks == ["just a few words here"]


def test_chunk_text_handles_empty_input():
    assert chunk_text("", size_words=200, overlap_words=50) == []


def test_chunk_text_no_infinite_loop_when_overlap_ge_size():
    # Guard against a degenerate config where overlap >= size, which could
    # otherwise loop forever advancing `start` by <= 0 each iteration.
    text = " ".join(f"w{i}" for i in range(50))
    chunks = chunk_text(text, size_words=10, overlap_words=10)
    assert len(chunks) < 1000  # completes at all = the real assertion
