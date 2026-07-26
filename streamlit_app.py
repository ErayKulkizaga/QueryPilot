import os
from typing import Any

import httpx
import streamlit as st

API_BASE_URL = os.getenv("QUERYPILOT_API_URL", "http://127.0.0.1:8000").rstrip("/")

SCENARIOS = {
    "E-posta filtresinde eksik indeks": {
        "scenario_id": "missing_customer_email_index",
        "sql": (
            "SELECT id, email, full_name FROM customers "
            "WHERE email = 'demo@example.com'"
        ),
    },
    "Müşteri sipariş geçmişi": {
        "scenario_id": "customer_order_history",
        "sql": (
            "SELECT c.email, o.created_at, o.total_amount "
            "FROM customers c JOIN orders o ON o.customer_id = c.id "
            "WHERE c.id BETWEEN 100 AND 120 ORDER BY o.created_at DESC"
        ),
    },
    "Son yedi günlük destek olayları": {
        "scenario_id": "recent_support_events",
        "sql": (
            "SELECT event_type, count(*) FROM support_events "
            "WHERE created_at >= now() - interval '7 days' GROUP BY event_type"
        ),
    },
}

CATEGORY_LABELS = {
    "potential_missing_index": "Eksik indeks sinyali",
    "expensive_nested_loop": "Pahalı nested loop",
    "disk_based_sort": "Diske taşan sıralama",
    "cardinality_misestimation": "Satır tahmin hatası",
    "no_clear_issue": "Belirgin sorun bulunamadı",
}

SEVERITY_LABELS = {
    "low": "Düşük",
    "medium": "Orta",
    "high": "Yüksek",
}


def _post(path: str, payload: dict[str, Any] | None, timeout: float) -> dict[str, Any]:
    try:
        response = httpx.post(
            f"{API_BASE_URL}{path}",
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json().get("detail", exc.response.text)
        except ValueError:
            detail = exc.response.text
        raise RuntimeError(str(detail)) from exc
    except httpx.RequestError as exc:
        raise RuntimeError(
            "QueryPilot servisine ulaşılamadı. Yerel API ve PostgreSQL çalışıyor mu?"
        ) from exc


def _render_report(report: dict[str, Any], *, enriched: bool) -> None:
    source = report["report_source"]
    if enriched and source == "foundry_local":
        st.success("Yerel model onaylı açıklama cümlelerini seçti.")
    elif enriched:
        st.info(
            "AI çıktısı kabul edilmedi; kanıta dayalı güvenli rapor korunuyor."
        )

    category_column, severity_column, latency_column = st.columns(3)
    category_column.metric(
        "Bulgu",
        CATEGORY_LABELS.get(report["issue_category"], report["issue_category"]),
    )
    severity_column.metric(
        "Önem",
        SEVERITY_LABELS.get(report["severity"], report["severity"]),
    )
    latency_column.metric("Yanıt süresi", f'{report["latency_ms"]} ms')

    st.subheader("Özet")
    st.write(report["summary"])

    if report["insufficient_context"]:
        st.warning(
            "Plan kanıtı güvenilir bir optimizasyon önermek için yeterli değil. "
            "QueryPilot bu nedenle öneri üretmedi."
        )
        return

    st.subheader("Plan kanıtı")
    for evidence in report["plan_evidence"]:
        st.markdown(f"- {evidence}")

    st.subheader("Öneri")
    st.write(report["recommendation"])
    if report.get("recommendation_sql"):
        st.code(report["recommendation_sql"], language="sql")

    citations = report.get("citations", [])
    if citations:
        st.subheader("Kaynaklar")
        for citation in citations:
            st.caption(
                f'{citation["title"]} · {citation["section"]} '
                f'({citation["document_id"]})'
            )


st.set_page_config(
    page_title="QueryPilot Local",
    page_icon="🧭",
    layout="wide",
)

st.title("QueryPilot Local")
st.caption(
    "PostgreSQL sorgu planını yerelde inceler; yalnızca planda kanıtlanan "
    "sorunlar için öneri verir."
)

with st.form("analysis-form"):
    mode = st.radio(
        "Sorgu kaynağı",
        ("Hazır senaryo", "Kendi SQL sorgum"),
        horizontal=True,
    )
    if mode == "Hazır senaryo":
        scenario_name = st.selectbox("Senaryo", list(SCENARIOS))
        scenario = SCENARIOS[scenario_name]
        st.code(scenario["sql"], language="sql")
        request_payload = {"scenario_id": scenario["scenario_id"]}
    else:
        sql = st.text_area(
            "Salt okunur SQL",
            height=180,
            placeholder="SELECT ...",
        )
        request_payload = {"sql": sql}
    submitted = st.form_submit_button(
        "Planı analiz et",
        type="primary",
        use_container_width=True,
    )

if submitted:
    st.session_state.pop("enrichment", None)
    with st.spinner("PostgreSQL planı ve kural kanıtları inceleniyor…"):
        try:
            st.session_state["analysis"] = _post(
                "/api/v1/analyses",
                request_payload,
                timeout=10,
            )
        except RuntimeError as exc:
            st.session_state.pop("analysis", None)
            st.error(str(exc))

analysis = st.session_state.get("analysis")
if analysis:
    st.divider()
    _render_report(analysis, enriched=False)

    if analysis["enrichment_available"]:
        st.divider()
        st.subheader("İsteğe bağlı yerel açıklama seçimi")
        st.caption(
            "Model yeni teknik metin yazamaz; yalnızca kural motorunun önceden "
            "onayladığı açıklama cümlelerini seçebilir. Geçersiz seçim reddedilir."
        )
        if st.button("Onaylı açıklamayı seç", use_container_width=True):
            with st.spinner(
                "Yerel model güvenli cümle havuzundan seçim yapıyor…"
            ):
                try:
                    st.session_state["enrichment"] = _post(
                        f'/api/v1/analyses/{analysis["analysis_id"]}/enrichment',
                        None,
                        timeout=120,
                    )
                except RuntimeError as exc:
                    st.error(str(exc))

    enrichment = st.session_state.get("enrichment")
    if enrichment:
        st.divider()
        _render_report(enrichment, enriched=True)

    with st.expander("Ham PostgreSQL planını göster"):
        st.json(analysis["raw_plan"])
