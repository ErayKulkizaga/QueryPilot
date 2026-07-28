from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_streamlit_app_renders_primary_analysis_form() -> None:
    app_path = Path(__file__).resolve().parents[1] / "streamlit_app.py"

    app = AppTest.from_file(str(app_path)).run(timeout=10)

    assert not app.exception
    assert app.title[0].value == "QueryPilot Local"
    assert app.button[0].label == "Planı analiz et"
    assert [tab.label for tab in app.tabs] == [
        "Plan analizi",
        "İş yükü öncelikleri",
        "Plan karşılaştırma",
    ]
    assert any(button.label == "İş yükünü yenile" for button in app.button)
