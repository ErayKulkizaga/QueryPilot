from __future__ import annotations

import os

from playwright.sync_api import Page, expect

APP_URL = os.getenv("QUERYPILOT_E2E_APP_URL", "http://127.0.0.1:8501")
REPRESENTATIVE_SQL = (
    "SELECT count(*) FROM orders WHERE total_amount > 250.00"
)


def test_workload_analysis_baseline_and_comparison(page: Page) -> None:
    page.goto(APP_URL, wait_until="domcontentloaded")
    expect(page.get_by_role("heading", name="QueryPilot Local")).to_be_visible(
        timeout=30_000
    )

    page.get_by_role("tab", name="İş yükü öncelikleri").click()
    page.get_by_role("button", name="İş yükünü yenile").click()

    representative_sql = page.get_by_label("Temsilî SQL", exact=True)
    expect(representative_sql).to_be_visible(timeout=15_000)
    representative_sql.fill(REPRESENTATIVE_SQL)

    approval = page.get_by_label(
        "SQL'i gözden geçirdim ve yalnızca yerel sentetik veritabanında "
        "EXPLAIN ANALYZE ile çalıştırmayı onaylıyorum.",
        exact=True,
    )
    # Streamlit renders a styled label over the native checkbox. Force targets
    # the accessible input while still exercising the browser event path.
    approval.check(force=True)

    analyze = page.get_by_role(
        "button",
        name="Temsilî SQL'i analiz et",
        exact=True,
    )
    expect(analyze).to_be_enabled()
    analyze.click()
    expect(
        page.get_by_text(
            "analiz edildi. Sonuç aşağıda baseline olarak kaydedilebilir.",
            exact=False,
        )
    ).to_be_visible(timeout=20_000)

    baseline_name = page.get_by_label("Baseline adı", exact=True)
    baseline_name.fill("UI E2E güvenli baseline")
    page.get_by_role(
        "button",
        name="Mevcut planı baseline olarak kaydet",
        exact=True,
    ).click()
    expect(
        page.get_by_text(
            "Baseline kaydedildi: UI E2E güvenli baseline",
            exact=True,
        )
    ).to_be_visible(timeout=15_000)

    page.get_by_role("tab", name="Plan karşılaştırma").click()
    expect(
        page.get_by_role("button", name="Baseline JSON indir", exact=True)
    ).to_be_visible(timeout=15_000)
    expect(
        page.get_by_role("button", name="Markdown raporu indir", exact=True)
    ).to_be_visible()

    page.get_by_role(
        "button",
        name="Son analizle karşılaştır",
        exact=True,
    ).click()
    expect(
        page.get_by_text(
            "Tanımlı eşiklere göre plan regresyonu bulunmadı.",
            exact=True,
        )
    ).to_be_visible(timeout=15_000)
