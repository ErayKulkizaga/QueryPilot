import json
import os
from typing import Any

import httpx
import streamlit as st

from app.analysis.workload_handoff import (
    RepresentativeSQLRequiredError,
    prepare_representative_sql,
)

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

MEASUREMENT_GROUP_LABELS = {
    "unspecified": "Kontrol edilmedi",
    "cold_cache": "Cold cache (ilk/disk ağırlıklı çalışma)",
    "warm_cache": "Warm cache (ısınmış/tekrarlı çalışma)",
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


def _get(path: str, timeout: float) -> dict[str, Any]:
    try:
        response = httpx.get(f"{API_BASE_URL}{path}", timeout=timeout)
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


def _get_text(path: str, timeout: float) -> str:
    try:
        response = httpx.get(f"{API_BASE_URL}{path}", timeout=timeout)
        response.raise_for_status()
        return response.text
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(exc.response.text) from exc
    except httpx.RequestError as exc:
        raise RuntimeError(
            "QueryPilot servisine ulaşılamadı. Yerel API çalışıyor mu?"
        ) from exc


def _delete(path: str, timeout: float) -> None:
    try:
        response = httpx.delete(f"{API_BASE_URL}{path}", timeout=timeout)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json().get("detail", exc.response.text)
        except ValueError:
            detail = exc.response.text
        raise RuntimeError(str(detail)) from exc
    except httpx.RequestError as exc:
        raise RuntimeError(
            "QueryPilot servisine ulaşılamadı. Yerel API çalışıyor mu?"
        ) from exc


def _render_report(report: dict[str, Any], *, enriched: bool) -> None:
    source = report["report_source"]
    if enriched and source == "foundry_local":
        st.success(
            "Foundry Local, plan kanıtı ve RAG kaynaklarından doğrulanan "
            "açıklamayı üretti."
        )
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


def _remember_analysis(
    request_payload: dict[str, str],
    analysis: dict[str, Any],
    *,
    workload_query_id: str | None = None,
    measurement_group: str = "unspecified",
) -> None:
    request_key = json.dumps(
        {
            "request": request_payload,
            "measurement_group": measurement_group,
        },
        sort_keys=True,
    )
    if st.session_state.get("analysis_history_key") != request_key:
        st.session_state["analysis_history_key"] = request_key
        st.session_state["analysis_history"] = []
    history = st.session_state.setdefault("analysis_history", [])
    history.append(analysis["analysis_id"])
    st.session_state["analysis_history"] = history[-9:]
    st.session_state["analysis"] = analysis
    st.session_state["analysis_workload_query_id"] = workload_query_id
    st.session_state["analysis_measurement_group"] = measurement_group
    st.session_state.pop("enrichment", None)


def _render_baseline_capture(analysis: dict[str, Any], *, key_prefix: str) -> None:
    st.divider()
    st.subheader("Plan baseline")
    st.caption(
        "Her analiz bir ölçüm örneği ekler. Baseline, aynı SQL için son dokuz "
        "örneğin medyanını yerel olarak saklar; sorguyu kendi başına yeniden "
        "çalıştırmaz ve optimizasyon önerisi üretmez."
    )
    history = st.session_state.get("analysis_history", [analysis["analysis_id"]])
    measurement_group = st.session_state.get(
        "analysis_measurement_group",
        "unspecified",
    )
    st.info(f"Bu sorgu için toplanan ölçüm örneği: {len(history)}")
    st.caption(
        "Ölçüm grubu: "
        f"{MEASUREMENT_GROUP_LABELS.get(measurement_group, measurement_group)}"
    )
    baseline_name = st.text_input(
        "Baseline adı",
        value="",
        placeholder="Örn. release-2.0 sipariş toplamı planı",
        key=f"{key_prefix}-baseline-name",
    )
    if st.button(
        "Mevcut planı baseline olarak kaydet",
        width="stretch",
        key=f"{key_prefix}-save-baseline",
    ):
        try:
            created = _post(
                "/api/v1/baselines",
                {
                    "analysis_ids": history,
                    "name": baseline_name,
                    "measurement_group": measurement_group,
                },
                timeout=10,
            )
            st.session_state["created_baseline"] = created
            st.session_state.pop("baselines", None)
            st.success(f'Baseline kaydedildi: {created["name"]}')
        except RuntimeError as exc:
            st.error(str(exc))


def _render_analysis_workspace() -> None:
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
        measurement_group = st.selectbox(
            "Ölçüm grubu",
            list(MEASUREMENT_GROUP_LABELS),
            format_func=MEASUREMENT_GROUP_LABELS.get,
            help=(
                "Bu seçim önbelleği değiştirmez; yalnızca kontrollü ölçüm "
                "koşulunu etiketler. Emin değilseniz Kontrol edilmedi bırakın."
            ),
        )
        submitted = st.form_submit_button(
            "Planı analiz et",
            type="primary",
            width="stretch",
        )

    if submitted:
        with st.spinner("PostgreSQL planı ve kural kanıtları inceleniyor…"):
            try:
                analysis = _post(
                    "/api/v1/analyses",
                    request_payload,
                    timeout=10,
                )
                _remember_analysis(
                    request_payload,
                    analysis,
                    measurement_group=measurement_group,
                )
            except RuntimeError as exc:
                st.session_state.pop("analysis", None)
                st.error(str(exc))

    analysis = st.session_state.get("analysis")
    if not analysis:
        return

    st.divider()
    _render_report(analysis, enriched=False)

    if analysis["enrichment_available"]:
        st.divider()
        st.subheader("Yerel AI + RAG açıklaması")
        st.caption(
            "Foundry Local, yalnızca kural motorunun plan kanıtlarını ve yerel "
            "RAG ile getirilen PostgreSQL kaynaklarını kullanarak doğal dilli "
            "açıklama üretir. Bilinmeyen kanıt, sayı veya kaynak reddedilir."
        )
        if st.button("AI açıklaması üret", width="stretch"):
            with st.spinner(
                "Yerel model plan kanıtı ve RAG kaynaklarıyla açıklama üretiyor…"
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

    _render_baseline_capture(analysis, key_prefix="analysis")


def _render_workload_workspace() -> None:
    st.subheader("İş yükü öncelikleri")
    st.write(
        "QueryPilot, PostgreSQL istatistiklerini toplam çalışma süresine göre "
        "sıralar. Bu liste bir optimizasyon önerisi değildir."
    )

    if st.button(
        "İş yükünü yenile",
        type="primary",
        width="stretch",
    ):
        with st.spinner("PostgreSQL iş yükü istatistikleri okunuyor…"):
            try:
                st.session_state["workload"] = _get(
                    "/api/v1/workload/queries?limit=10",
                    timeout=10,
                )
            except RuntimeError as exc:
                st.session_state.pop("workload", None)
                st.error(str(exc))

    workload = st.session_state.get("workload")
    if not workload:
        st.info(
            "Henüz istatistik yüklenmedi. PostgreSQL çalışırken İş yükünü "
            "yenile düğmesine basın."
        )
        return

    queries = workload["queries"]
    if not queries:
        st.info(
            "En az iki kez çalışmış uygun bir SELECT sorgusu bulunamadı."
        )
        return

    st.caption(
        "Sıralama ölçütü: toplam çalışma süresi. İstatistikler öneri veya "
        "şema değişikliği üretmez."
    )
    st.dataframe(
        [
            {
                "Sıra": query["rank"],
                "Çağrı": query["calls"],
                "Toplam süre (ms)": query["total_exec_time_ms"],
                "Ortalama süre (ms)": query["mean_exec_time_ms"],
                "Okunan blok": query["shared_blocks_read"],
                "Geçici blok": query["temp_blocks_written"],
            }
            for query in queries
        ],
        hide_index=True,
        width="stretch",
    )

    selected_rank = st.selectbox(
        "İncelenecek aday",
        [query["rank"] for query in queries],
        format_func=lambda rank: (
            f"#{rank} · "
            f'{next(query["total_exec_time_ms"] for query in queries if query["rank"] == rank)} ms'
        ),
    )
    selected = next(
        query for query in queries if query["rank"] == selected_rank
    )
    st.code(selected["normalized_sql"], language="sql")
    st.caption(selected["ranking_reason"])

    if selected["requires_representative_sql"]:
        st.warning(
            "PostgreSQL bu sorgudaki sabitleri $1, $2 gibi parametrelere "
            "dönüştürmüş. Plan analizi için gerçek parametreleri içeren temsili "
            "SQL sorgusunu aşağıda hazırlayın."
        )
    else:
        st.info(
            "İstatistik yalnızca sorgunun önceliğini gösterir. Aşağıdaki SQL "
            "açıkça onaylanmadan çalıştırılmaz."
        )

    representative_sql = st.text_area(
        "Temsilî SQL",
        value=selected["normalized_sql"],
        height=180,
        key=f'workload-sql-{selected["query_id"]}',
        help=(
            "Bu metni yerel sentetik veritabanına uygun gerçek örnek değerlerle "
            "düzenleyin. $1, $2 gibi yer tutucular kabul edilmez."
        ),
    )
    try:
        prepared_sql = prepare_representative_sql(representative_sql)
        representative_sql_ready = True
    except RepresentativeSQLRequiredError as exc:
        prepared_sql = ""
        representative_sql_ready = False
        st.warning(str(exc))

    reviewed = st.checkbox(
        "SQL'i gözden geçirdim ve yalnızca yerel sentetik veritabanında "
        "EXPLAIN ANALYZE ile çalıştırmayı onaylıyorum.",
        key=f'workload-review-{selected["query_id"]}',
    )
    workload_measurement_group = st.selectbox(
        "Temsilî sorgu ölçüm grubu",
        list(MEASUREMENT_GROUP_LABELS),
        format_func=MEASUREMENT_GROUP_LABELS.get,
        key=f'workload-group-{selected["query_id"]}',
        help=(
            "QueryPilot önbelleği temizlemez. Cold veya warm seçimi yalnızca "
            "ölçüm koşulunu sizin kontrol ettiğinizi kaydeder."
        ),
    )
    analyze_workload = st.button(
        "Temsilî SQL'i analiz et",
        type="primary",
        width="stretch",
        disabled=not (reviewed and representative_sql_ready),
        key=f'workload-analyze-{selected["query_id"]}',
    )
    if analyze_workload:
        request_payload = {"sql": prepared_sql}
        with st.spinner("Temsilî sorgunun PostgreSQL planı inceleniyor…"):
            try:
                analysis = _post(
                    "/api/v1/analyses",
                    request_payload,
                    timeout=10,
                )
                _remember_analysis(
                    request_payload,
                    analysis,
                    workload_query_id=selected["query_id"],
                    measurement_group=workload_measurement_group,
                )
                st.success(
                    f'İş yükü adayı #{selected["rank"]} analiz edildi. '
                    "Sonuç aşağıda baseline olarak kaydedilebilir."
                )
            except RuntimeError as exc:
                st.error(str(exc))

    workload_analysis = st.session_state.get("analysis")
    if (
        workload_analysis
        and st.session_state.get("analysis_workload_query_id")
        == selected["query_id"]
    ):
        st.divider()
        _render_report(workload_analysis, enriched=False)
        with st.expander("Ham PostgreSQL planını göster"):
            st.json(workload_analysis["raw_plan"])
        _render_baseline_capture(
            workload_analysis,
            key_prefix=f'workload-{selected["query_id"]}',
        )


def _render_baseline_workspace() -> None:
    st.subheader("Plan karşılaştırma")
    st.write(
        "Aynı normalize SQL için kaydedilmiş baseline ile en son planı "
        "deterministik olarak karşılaştırır. Fark tek başına optimizasyon "
        "önerisi üretmez."
    )

    uploaded_baseline = st.file_uploader(
        "Baseline JSON içe aktar",
        type=("json",),
        help=(
            "Yalnızca QueryPilot tarafından dışa aktarılan, en fazla 256 KB "
            "boyutundaki baseline dosyaları kabul edilir."
        ),
    )
    if uploaded_baseline is not None:
        raw_upload = uploaded_baseline.getvalue()
        if len(raw_upload) > 256_000:
            st.error("Baseline dosyası 256 KB sınırını aşıyor.")
        elif st.button("Yüklenen baseline'ı içe aktar", width="stretch"):
            try:
                import_payload = json.loads(raw_upload.decode("utf-8"))
                if not isinstance(import_payload, dict):
                    raise ValueError("Baseline JSON bir nesne olmalıdır.")
                imported = _post(
                    "/api/v1/baselines/imports",
                    import_payload,
                    timeout=10,
                )
                st.session_state.pop("baselines", None)
                st.success(f'Baseline içe aktarıldı: {imported["name"]}')
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                st.error(f"Geçersiz baseline dosyası: {exc}")
            except RuntimeError as exc:
                st.error(str(exc))

    if st.button("Baseline listesini yenile", type="primary", width="stretch"):
        try:
            st.session_state["baselines"] = _get(
                "/api/v1/baselines?limit=50",
                timeout=10,
            )
        except RuntimeError as exc:
            st.session_state.pop("baselines", None)
            st.error(str(exc))

    baseline_payload = st.session_state.get("baselines")
    if baseline_payload is None:
        try:
            baseline_payload = _get("/api/v1/baselines?limit=50", timeout=10)
            st.session_state["baselines"] = baseline_payload
        except RuntimeError:
            st.info(
                "Baseline listesi henüz yüklenmedi. Yerel API çalışırken "
                "listeyi yenileyin."
            )
            return

    baselines = baseline_payload["baselines"]
    if not baselines:
        st.info(
            "Henüz plan baseline'ı yok. Önce Plan analizi sekmesinde bir "
            "analizi baseline olarak kaydedin."
        )
        return

    selected_id = st.selectbox(
        "Baseline",
        [baseline["baseline_id"] for baseline in baselines],
        format_func=lambda baseline_id: next(
            baseline["name"]
            for baseline in baselines
            if baseline["baseline_id"] == baseline_id
        ),
    )
    selected = next(
        baseline
        for baseline in baselines
        if baseline["baseline_id"] == selected_id
    )
    st.code(selected["normalized_sql"], language="sql")
    baseline_time, baseline_cost, baseline_nodes = st.columns(3)
    baseline_time.metric(
        "Baseline süre",
        f'{selected["execution_time_ms"]:.3f} ms',
    )
    baseline_cost.metric("Baseline maliyet", f'{selected["root_total_cost"]:.3f}')
    baseline_nodes.metric("Baseline düğüm", selected["node_count"])
    st.caption(f'Baseline örnek sayısı: {selected["sample_count"]}')
    selected_group = selected["measurement_group"]
    st.caption(
        "Ölçüm grubu: "
        f"{MEASUREMENT_GROUP_LABELS.get(selected_group, selected_group)}"
    )
    try:
        portable_baseline = _get(
            f"/api/v1/baselines/{selected_id}/export",
            timeout=10,
        )
        baseline_report = _get_text(
            f"/api/v1/baselines/{selected_id}/report",
            timeout=10,
        )
        export_column, report_column = st.columns(2)
        export_column.download_button(
            "Baseline JSON indir",
            data=json.dumps(
                portable_baseline,
                indent=2,
                ensure_ascii=False,
            ),
            file_name=f"querypilot-baseline-{selected_id}.json",
            mime="application/json",
            width="stretch",
        )
        report_column.download_button(
            "Markdown raporu indir",
            data=baseline_report,
            file_name=f"querypilot-baseline-{selected_id}.md",
            mime="text/markdown",
            width="stretch",
        )
    except RuntimeError as exc:
        st.warning(f"Dışa aktarma hazırlanamadı: {exc}")

    delete_confirmed = st.checkbox(
        "Seçili baseline'ı kalıcı olarak silmek istediğimi onaylıyorum.",
        key=f"delete-confirm-{selected_id}",
    )
    if st.button(
        "Seçili baseline'ı sil",
        disabled=not delete_confirmed,
        width="stretch",
    ):
        try:
            _delete(f"/api/v1/baselines/{selected_id}", timeout=10)
            st.session_state.pop("baselines", None)
            st.session_state.pop("comparison", None)
            st.success("Baseline silindi. Listeyi yenileyebilirsiniz.")
            return
        except RuntimeError as exc:
            st.error(str(exc))

    analysis = st.session_state.get("analysis")
    if not analysis:
        st.warning(
            "Karşılaştırma için Plan analizi sekmesinde aynı SQL'i yeniden "
            "analiz edin."
        )
        return

    if st.button("Son analizle karşılaştır", width="stretch"):
        try:
            current_history = st.session_state.get(
                "analysis_history",
                [analysis["analysis_id"]],
            )
            st.session_state["comparison"] = _post(
                f"/api/v1/baselines/{selected_id}/comparisons",
                {
                    "analysis_ids": current_history,
                    "measurement_group": st.session_state.get(
                        "analysis_measurement_group",
                        "unspecified",
                    ),
                },
                timeout=10,
            )
        except RuntimeError as exc:
            st.session_state.pop("comparison", None)
            st.error(str(exc))

    comparison = st.session_state.get("comparison")
    if not comparison or comparison["baseline_id"] != selected_id:
        return

    st.divider()
    current_time, time_delta, cost_delta, node_delta = st.columns(4)
    current_time.metric(
        "Güncel süre",
        f'{comparison["current_execution_time_ms"]:.3f} ms',
    )
    time_delta.metric(
        "Süre farkı",
        f'{comparison["execution_time_delta_ms"]:+.3f} ms',
    )
    cost_delta.metric(
        "Maliyet farkı",
        f'{comparison["root_cost_delta"]:+.3f}',
    )
    node_delta.metric("Düğüm farkı", f'{comparison["node_count_delta"]:+d}')
    st.caption(
        f'Medyan örnekleri: baseline {comparison["baseline_sample_count"]}, '
        f'güncel {comparison["current_sample_count"]}.'
    )
    current_group = comparison["current_measurement_group"]
    st.caption(
        "Ölçüm grubu: "
        f"{MEASUREMENT_GROUP_LABELS.get(current_group, current_group)}"
    )

    if comparison["regression_detected"]:
        st.error("Kanıt eşiğini aşan plan regresyonu tespit edildi.")
        for reason in comparison["regression_reasons"]:
            st.markdown(f"- {reason}")
    else:
        st.success("Tanımlı eşiklere göre plan regresyonu bulunmadı.")

    if comparison["node_changes"]:
        st.subheader("Plan yapısı farkları")
        st.dataframe(comparison["node_changes"], hide_index=True, width="stretch")
    st.caption(
        "Bu karşılaştırma öneri üretmez. Sonuçlar aynı sorgu ve temsilî iş "
        "yükü altında insan incelemesiyle değerlendirilmelidir."
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

analysis_tab, workload_tab, baseline_tab = st.tabs(
    ("Plan analizi", "İş yükü öncelikleri", "Plan karşılaştırma")
)

with analysis_tab:
    _render_analysis_workspace()

with workload_tab:
    _render_workload_workspace()

with baseline_tab:
    _render_baseline_workspace()
