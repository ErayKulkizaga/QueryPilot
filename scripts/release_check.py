from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

from app import __version__

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DEMO = ROOT / "public-demo"
RELEASE_VERSION = "1.0.0"

REQUIRED_FILES = (
    ROOT / "README.md",
    ROOT / "docs" / "architecture.md",
    ROOT / "docs" / "demo-script.md",
    ROOT / "docs" / "release-checklist.md",
    ROOT / "docs" / "technical-spike.md",
    ROOT / "evaluation" / "results.json",
    ROOT / "evaluation" / "api_smoke_result.json",
    ROOT / "evaluation" / "api_scenario_smoke_result.json",
    ROOT / "evaluation" / "before_after_benchmark.json",
    ROOT / "evaluation" / "workload_smoke_result.json",
    ROOT / "evaluation" / "baseline_smoke_result.json",
    ROOT / "evaluation" / "security_audit.json",
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


def verify_release_versions() -> None:
    with (ROOT / "pyproject.toml").open("rb") as stream:
        python_version = tomllib.load(stream)["project"]["version"]
    with (PUBLIC_DEMO / "package.json").open(encoding="utf-8") as stream:
        public_version = json.load(stream)["version"]

    versions = {
        "app": __version__,
        "python package": python_version,
        "public demo": public_version,
    }
    mismatches = {
        name: version for name, version in versions.items() if version != RELEASE_VERSION
    }
    if mismatches:
        rendered = ", ".join(f"{name}={version}" for name, version in mismatches.items())
        raise SystemExit(f"Release version mismatch; expected {RELEASE_VERSION}: {rendered}")
    print(f"[version] all release surfaces report {RELEASE_VERSION}")


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
    verify_release_versions()
    run("tracked secret scan", [sys.executable, "-m", "scripts.secret_scan"])
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
