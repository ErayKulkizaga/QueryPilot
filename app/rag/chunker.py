import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

_HEADING = re.compile(r"^(#{2,4})\s+(.+?)\s*$")
_TOKEN = re.compile(r"\w+|[^\w\s]", re.UNICODE)
_SLUG_CHARACTER = re.compile(r"[^a-z0-9]+")


class KnowledgeDocumentError(ValueError):
    """Raised when a knowledge document does not follow the local contract."""


@dataclass(frozen=True, slots=True)
class KnowledgeChunk:
    chunk_id: str
    document_id: str
    title: str
    section: str
    text: str
    source_path: str
    source_url: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_frontmatter(content: str, path: Path) -> tuple[dict[str, str], str]:
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        raise KnowledgeDocumentError(f"{path.name} is missing YAML-style frontmatter.")
    try:
        closing_index = next(
            index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---"
        )
    except StopIteration as exc:
        raise KnowledgeDocumentError(f"{path.name} has unclosed frontmatter.") from exc

    metadata: dict[str, str] = {}
    for line in lines[1:closing_index]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, separator, value = line.partition(":")
        if not separator or not key.strip() or not value.strip():
            raise KnowledgeDocumentError(
                f"{path.name} contains invalid frontmatter line: {line!r}"
            )
        metadata[key.strip()] = value.strip().strip("\"'")

    required = {"document_id", "title", "source_url"}
    missing = required - metadata.keys()
    if missing:
        raise KnowledgeDocumentError(
            f"{path.name} is missing metadata fields: {sorted(missing)}"
        )
    return metadata, "\n".join(lines[closing_index + 1 :]).strip()


def _slug(value: str) -> str:
    slug = _SLUG_CHARACTER.sub("-", value.lower()).strip("-")
    return slug or "section"


def _tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text)


def _untokenize(tokens: list[str]) -> str:
    text = " ".join(tokens)
    return re.sub(r"\s+([,.;:!?%)\]])", r"\1", text).replace("( ", "(").replace("[ ", "[")


def _split_text(text: str, *, max_tokens: int, overlap_tokens: int) -> list[str]:
    tokens = _tokenize(text)
    if len(tokens) <= max_tokens:
        return [text.strip()]

    chunks: list[str] = []
    start = 0
    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        if end < len(tokens):
            sentence_floor = max(start + max_tokens // 2, start + 1)
            for candidate in range(end, sentence_floor, -1):
                if tokens[candidate - 1] in {".", "!", "?"}:
                    end = candidate
                    break
        chunks.append(_untokenize(tokens[start:end]).strip())
        if end >= len(tokens):
            break
        start = max(end - overlap_tokens, start + 1)
    return chunks


def chunk_document(
    path: Path,
    *,
    knowledge_root: Path,
    max_tokens: int = 420,
    overlap_tokens: int = 50,
) -> list[KnowledgeChunk]:
    if max_tokens < 50:
        raise ValueError("max_tokens must be at least 50.")
    if overlap_tokens < 0 or overlap_tokens >= max_tokens:
        raise ValueError("overlap_tokens must be between 0 and max_tokens.")

    metadata, body = _parse_frontmatter(path.read_text(encoding="utf-8"), path)
    current_hierarchy: list[str] = []
    section_lines: list[str] = []
    sections: list[tuple[str, str]] = []

    def flush_section() -> None:
        text = "\n".join(section_lines).strip()
        if text:
            section = " > ".join(current_hierarchy) if current_hierarchy else "Overview"
            sections.append((section, text))
        section_lines.clear()

    for line in body.splitlines():
        heading = _HEADING.match(line)
        if heading:
            flush_section()
            level = len(heading.group(1))
            hierarchy_index = level - 2
            current_hierarchy[hierarchy_index:] = [heading.group(2).strip()]
        elif line.startswith("# "):
            continue
        else:
            section_lines.append(line)
    flush_section()

    chunks: list[KnowledgeChunk] = []
    relative_path = path.relative_to(knowledge_root).as_posix()
    for section, text in sections:
        parts = _split_text(
            text,
            max_tokens=max_tokens,
            overlap_tokens=overlap_tokens,
        )
        for part_index, part in enumerate(parts, start=1):
            chunks.append(
                KnowledgeChunk(
                    chunk_id=(
                        f"{metadata['document_id']}:{_slug(section)}:{part_index:02d}"
                    ),
                    document_id=metadata["document_id"],
                    title=metadata["title"],
                    section=section,
                    text=part,
                    source_path=relative_path,
                    source_url=metadata["source_url"],
                )
            )
    if not chunks:
        raise KnowledgeDocumentError(f"{path.name} does not contain chunkable sections.")
    return chunks


def chunk_knowledge_base(
    knowledge_root: Path,
    *,
    max_tokens: int = 420,
    overlap_tokens: int = 50,
) -> list[KnowledgeChunk]:
    paths = sorted(knowledge_root.glob("*.md"))
    if not paths:
        raise KnowledgeDocumentError(f"No Markdown documents found under {knowledge_root}.")

    chunks: list[KnowledgeChunk] = []
    document_ids: set[str] = set()
    for path in paths:
        document_chunks = chunk_document(
            path,
            knowledge_root=knowledge_root,
            max_tokens=max_tokens,
            overlap_tokens=overlap_tokens,
        )
        document_id = document_chunks[0].document_id
        if document_id in document_ids:
            raise KnowledgeDocumentError(f"Duplicate document_id: {document_id}")
        document_ids.add(document_id)
        chunks.extend(document_chunks)
    return chunks

