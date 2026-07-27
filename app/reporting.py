from functools import lru_cache
from pathlib import Path

from app.analysis.rule_engine import RuleAnalysis
from app.config import Settings
from app.llm.foundry_client import FoundryLocalClient
from app.llm.generator import GenerationResult, GroundedReportGenerator
from app.rag.embedder import FoundryEmbedder
from app.rag.index import VectorIndex
from app.rag.retriever import Retriever

ROOT = Path(__file__).resolve().parents[1]
_active_reporting_service: "ReportingService | None" = None


class ReportingService:
    def __init__(
        self,
        *,
        client: FoundryLocalClient,
        retriever: Retriever,
        repair_cutoff_seconds: float,
    ) -> None:
        self._retriever = retriever
        self._generator = GroundedReportGenerator(
            client,
            repair_cutoff_seconds=repair_cutoff_seconds,
        )

    def generate(self, analysis: RuleAnalysis) -> GenerationResult:
        finding = analysis.primary
        retrieval_query = "\n".join(
            [
                finding.category.value,
                finding.summary,
                *finding.evidence,
            ]
        )
        sources = self._retriever.retrieve(retrieval_query, top_k=3)
        return self._generator.generate(analysis=analysis, sources=sources)

    def close(self) -> None:
        self._generator.close()


@lru_cache(maxsize=1)
def _build_reporting_service(
    *,
    app_name: str,
    chat_model_alias: str,
    embedding_model_alias: str,
    repair_cutoff_seconds: float,
) -> ReportingService:
    global _active_reporting_service
    index_root = ROOT / "data" / "index"
    index = VectorIndex.load(
        vectors_path=index_root / "querypilot_embeddings.npz",
        metadata_path=index_root / "querypilot_chunks.json",
    )
    client = FoundryLocalClient(
        app_name=app_name,
        chat_model_alias=chat_model_alias,
        embedding_model_alias=embedding_model_alias,
    )
    _active_reporting_service = ReportingService(
        client=client,
        retriever=Retriever(index=index, embedder=FoundryEmbedder(client)),
        repair_cutoff_seconds=repair_cutoff_seconds,
    )
    return _active_reporting_service


def get_reporting_service(settings: Settings) -> ReportingService:
    return _build_reporting_service(
        app_name=settings.foundry_app_name,
        chat_model_alias=settings.foundry_chat_model,
        embedding_model_alias=settings.foundry_embedding_model,
        repair_cutoff_seconds=settings.generation_repair_cutoff_seconds,
    )


def shutdown_reporting_service() -> None:
    global _active_reporting_service
    if _active_reporting_service is not None:
        _active_reporting_service.close()
        _active_reporting_service = None
    _build_reporting_service.cache_clear()
