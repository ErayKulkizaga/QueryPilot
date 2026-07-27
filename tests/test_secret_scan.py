from pathlib import Path

from scripts.secret_scan import ROOT, scan_paths


def test_secret_scan_detects_private_key(tmp_path: Path) -> None:
    candidate = tmp_path / "leaked.txt"
    candidate.write_text(
        "-----BEGIN " + "PRIVATE KEY-----\nnot-a-real-key\n",
        encoding="utf-8",
    )

    original_root = candidate.relative_to(ROOT) if candidate.is_relative_to(ROOT) else None
    if original_root is None:
        # scan_paths intentionally reports workspace-relative paths, so exercise
        # the pattern directly through a temporary tracked-style file.
        candidate = ROOT / "tmp" / "secret-scan-test.txt"
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_text(
            "-----BEGIN " + "PRIVATE KEY-----\nnot-a-real-key\n",
            encoding="utf-8",
        )
    try:
        findings = scan_paths([candidate])
    finally:
        if candidate.is_relative_to(ROOT):
            candidate.unlink(missing_ok=True)

    assert [(item.kind, item.line) for item in findings] == [("private-key", 1)]
