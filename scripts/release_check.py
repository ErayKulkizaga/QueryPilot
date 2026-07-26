from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DEMO = ROOT / "public-demo"

REQUIRED_FILES = (
    ROOT / "README.md",
    ROOT / "docs" / "architecture.md",
    ROOT / "docs" / "demo-script.md",
    ROOT / "docs" / "release-checklist.md",
    ROOT / "docs" / "technical-spike.md",
    ROOT / "evaluation" / "results_qwen2.5-1.5b.json",
    ROOT / "artifacts" / "QueryPilot_Local_Teknik_Sunum.pptx",
    ROOT / "artifacts" / "QueryPilot_Local_Teknik_Sunum.pdf",
    ROOT / "artifacts" / "screenshots" / "querypilot-live-desktop.png",
    ROOT / "artifacts" / "screenshots" / "querypilot-live-mobile.png",
    PUBLIC_DEMO / ".openai" / "hosting.json",
)


def run(label: str, command: list[str], *, cwd: Path = ROOT) -> None:
    print(f"\n[{label}] {' '.join(command)}")
    subprocess.run(command, cwd=cwd, check=True)


def verify_required_files() -> None:
    missing = [path.relative_to(ROOT) for path in REQUIRED_FILES if not path.is_file()]
    if missing:
        rendered = ", ".join(str(path) for path in missing)
        raise SystemExit(f"Missing required release files: {rendered}")
    print(f"[artifacts] {len(REQUIRED_FILES)} required files present")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run QueryPilot's release gate without starting Docker."
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run the API smoke test against services that are already available.",
    )
    parser.add_argument(
        "--skip-public",
        action="store_true",
        help="Skip public-demo lint/build/tests when Node dependencies are unavailable.",
    )
    return parser.parse_args()


def npm_executable() -> str:
    executable = shutil.which("npm.cmd") or shutil.which("npm")
    if executable is None:
        raise SystemExit("npm is required for public-demo checks but was not found.")
    return executable


def main() -> None:
    args = parse_args()
    verify_required_files()
    run("python tests", [sys.executable, "-m", "pytest"])
    run("python lint", [sys.executable, "-m", "ruff", "check", "."])

    if not args.skip_public:
        npm = npm_executable()
        run("public lint", [npm, "run", "lint"], cwd=PUBLIC_DEMO)
        run("public build and tests", [npm, "test"], cwd=PUBLIC_DEMO)

    if args.live:
        run("live API smoke", [sys.executable, "-m", "scripts.api_smoke"])

    print("\nRelease gate passed.")


if __name__ == "__main__":
    main()
