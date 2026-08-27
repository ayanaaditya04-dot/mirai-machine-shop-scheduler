from streamlit.testing.v1 import AppTest
from pathlib import Path


APP = Path(__file__).resolve().parents[1] / "app.py"


def test_dashboard_briefing_tabs_and_downloads():
    app = AppTest.from_file(APP).run(timeout=30)
    assert not app.exception
    assert app.title[0].value == "6 AM SHIFT BRIEFING"
    assert [tab.label for tab in app.tabs] == [
        "6 AM SHIFT BRIEFING", "Schedule", "Orders", "Disruptions", "Cost & Trade-offs", "Final Recommendation"
    ]
    assert {button.label for button in app.download_button} >= {
        "Download current schedule CSV", "Download order summary CSV", "Download cost comparison CSV"
    }


def test_dashboard_defense_button_runs_real_replanner():
    app = AppTest.from_file(APP).run(timeout=30)
    app.button[1].click().run(timeout=30)
    assert not app.exception
    assert any("Replan accepted" in item.value for item in app.success)
    assert any(item.label == "Download disruption impact" for item in app.download_button)