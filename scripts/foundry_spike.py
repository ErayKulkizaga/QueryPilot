import argparse
import json
import re
from collections.abc import Callable

from app.config import get_settings
from app.llm.foundry_client import FoundryLocalClient


def progress(label: str) -> Callable[[float], None]:
    last_bucket = -1

    def report(value: float) -> None:
        nonlocal last_bucket
        bucket = int(value) // 5
        if bucket != last_bucket:
            last_bucket = bucket
            print(f"{label}: {value:.1f}%", flush=True)

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify Foundry Local chat and embeddings.")
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download missing models before running inference.",
    )
    args = parser.parse_args()
    settings = get_settings()

    with FoundryLocalClient(
        app_name=settings.foundry_app_name,
        chat_model_alias=settings.foundry_chat_model,
        embedding_model_alias=settings.foundry_embedding_model,
    ) as client:
        print(json.dumps({"before": client.model_status()}, indent=2), flush=True)
        embeddings = client.embed(
            [
                "A selective sequential scan can indicate a missing index.",
                "An external merge sort uses temporary disk space.",
            ],
            download=args.download,
            progress_callback=progress("embedding-model"),
        )
        chat = client.complete(
            [
                {
                    "role": "system",
                    "content": "Reply with one short sentence. Do not invent plan facts.",
                },
                {
                    "role": "user",
                    "content": (
                        "Explain this evidence: Seq Scan on customers; "
                        "Rows Removed by Filter: 24999."
                    ),
                },
            ],
            download=args.download,
            progress_callback=progress("chat-model"),
        )
        response_numbers = {
            int(value.replace(",", ""))
            for value in re.findall(r"\d[\d,]*", chat)
        }
        expected_numbers = {24_999}
        print(
            json.dumps(
                {
                    "embedding_count": len(embeddings),
                    "embedding_dimensions": len(embeddings[0]),
                    "chat": chat,
                    "numeric_integrity": response_numbers == expected_numbers,
                    "expected_numbers": sorted(expected_numbers),
                    "response_numbers": sorted(response_numbers),
                    "after": client.model_status(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
