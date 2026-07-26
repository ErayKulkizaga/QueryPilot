from pathlib import Path

import pytest

from app.rag.chunker import (
    KnowledgeDocumentError,
    chunk_document,
    chunk_knowledge_base,
)

ROOT = Path(__file__).resolve().parents[1]


def test_chunks_all_knowledge_documents_with_stable_metadata() -> None:
    chunks = chunk_knowledge_base(ROOT / "knowledge")

    assert len(chunks) >= 20
    assert len({chunk.document_id for chunk in chunks}) == 6
    assert len({chunk.chunk_id for chunk in chunks}) == len(chunks)
    assert all(chunk.section for chunk in chunks)
    assert all(chunk.source_url.startswith("https://www.postgresql.org/") for chunk in chunks)
    assert all(chunk.source_path.endswith(".md") for chunk in chunks)


def test_splits_long_section_with_overlap(tmp_path: Path) -> None:
    document = tmp_path / "long.md"
    document.write_text(
        "---\n"
        "document_id: test-01\n"
        "title: Test Document\n"
        "source_url: https://example.test/source\n"
        "---\n"
        "# Test\n"
        "## Long section\n"
        + " ".join(f"token{index}" for index in range(160)),
        encoding="utf-8",
    )

    chunks = chunk_document(
        document,
        knowledge_root=tmp_path,
        max_tokens=60,
        overlap_tokens=10,
    )

    assert len(chunks) >= 3
    assert chunks[0].section == "Long section"
    assert "token50" in chunks[0].text
    assert "token50" in chunks[1].text


def test_rejects_missing_frontmatter(tmp_path: Path) -> None:
    document = tmp_path / "invalid.md"
    document.write_text("# Invalid\n\n## Section\nText", encoding="utf-8")

    with pytest.raises(KnowledgeDocumentError):
        chunk_document(document, knowledge_root=tmp_path)

