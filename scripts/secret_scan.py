from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_TEXT_FILE_BYTES = 1_000_000
BLOCKED_FILENAMES = {
    ".env",
    "id_rsa",
    "id_ed25519",
}
BLOCKED_SUFFIXES = {
    ".key",
    ".p12",
    ".pfx",
    ".pem",
}
SECRET_PATTERNS = {
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "aws-access-key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "github-token": re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}\b"),
    "github-fine-grained-token": re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b"),
    "openai-api-key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "slack-token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
}


@dataclass(frozen=True)
class Finding:
    path: str
    kind: str
    line: int | None = None


def tracked_files() -> list[Path]:
    completed = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={ROOT.as_posix()}",
            "ls-files",
            "-z",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [
        ROOT / item.decode("utf-8")
        for item in completed.stdout.split(b"\0")
        if item
    ]


def scan_paths(paths: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        if path.name in BLOCKED_FILENAMES or path.suffix.lower() in BLOCKED_SUFFIXES:
            findings.append(Finding(path=relative, kind="blocked-secret-file"))
            continue
        if not path.is_file() or path.stat().st_size > MAX_TEXT_FILE_BYTES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            for kind, pattern in SECRET_PATTERNS.items():
                if pattern.search(line):
                    findings.append(Finding(path=relative, kind=kind, line=line_number))
    return findings


def main() -> None:
    paths = tracked_files()
    findings = scan_paths(paths)
    if findings:
        for finding in findings:
            location = f"{finding.path}:{finding.line}" if finding.line else finding.path
            print(f"{location}: {finding.kind}")
        raise SystemExit(f"Tracked secret scan failed with {len(findings)} finding(s).")
    print(f"Tracked secret scan passed across {len(paths)} files.")


if __name__ == "__main__":
    main()
