from __future__ import annotations

from io import BytesIO
from zipfile import ZipFile
from unittest.mock import Mock

from lxml import etree
from PIL import Image
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from src.analytics.player_cards import build_player_card, load_player_cards
from src.reports.branding import CONTACT_EMAIL, FOOTER_URL, STATSBOMB_CREDIT
from src.reports.player_cards_export import player_cards_docx, player_cards_html, player_cards_pdf
from src.ui.player_card_charts import render_player_cards_png
from src.ui import player_cards_panel

MATCH = {
    "match_id": 1,
    "home_team_name": "Local",
    "away_team_name": "Visitante",
    "home_score": 1,
    "away_score": 0,
    "competition_name": "Copa",
    "match_date": "2026-11-13",
}


def event(kind, player=1, minute=10, **data):
    return {
        "type": {"name": kind},
        "player": {"id": player, "name": f"Jugador {player}"},
        "team": {"id": 10 if (player or 0) < 3 else 20, "name": "Local" if (player or 0) < 3 else "Visitante"},
        "position": {"name": "Goalkeeper"},
        "period": 1,
        "minute": minute,
        **data,
    }


@pytest.fixture
def card():
    events = [
        event("Pass", location=[70, 40], **{"pass": {"end_location": [105, 40], "length": 35, "shot_assist": True}}),
        event(
            "Pass",
            location=[75, 40],
            **{"pass": {"end_location": [100, 40], "length": 25, "outcome": {"name": "Incomplete"}}},
        ),
        event("Pass", **{"pass": {"length": 40}}),  # Counts in totals, never invents map coordinates.
        event("Pass", location=[100, 40], **{"pass": {"end_location": [110, 40], "length": 10}}),
        event("Shot", shot={"outcome": {"name": "Goal"}, "statsbomb_xg": 0.42}),
        event("Shot", period=5, shot={"outcome": {"name": "Goal"}, "statsbomb_xg": 0.76}),
        event("Dribble", dribble={"outcome": {"name": "Complete"}}),
        event("Dribble", dribble={"outcome": {"name": "Incomplete"}}),
        event("Duel", duel={"type": {"name": "Tackle"}, "outcome": {"name": "Success In Play"}}),
        event("Duel", duel={"type": {"name": "Tackle"}, "outcome": {"name": "Lost In Play"}}),
        event("Carry", location=[10, 20], carry={"end_location": [20, 20]}),
        event("Carry", location=[20, 20], carry={"end_location": [10, 20]}),
        event("Carry", location=[10, 20], carry={"end_location": [200, 20]}),
        event("Ball Receipt*", location=[20, 30]),
        event("Ball Receipt*", location=[20, 30], ball_receipt={"outcome": {"name": "Incomplete"}}),
        event("Ball Recovery", location=[25, 30]),
        event("Ball Recovery", location=[25, 30], ball_recovery={"recovery_failure": True}),
        event("Foul Committed", foul_committed={"card": {"name": "Yellow Card"}}),
        event("Bad Behaviour", minute=70, bad_behaviour={"card": {"name": "Second Yellow"}}),
        event("Pressure"),
        event("Block"),
        event("Clearance"),
        event("Dispossessed"),
        event("Dribbled Past"),
        event("Miscontrol"),
        event("Foul Won"),
        event("Half End", player=None, minute=95, period=2),
    ]
    return build_player_card(MATCH, events, [{"player_id": 1, "starter": True}], 1)


def test_event_metrics_keep_attempts_outcomes_and_shootouts_separate(card):
    assert card["stats"] == {
        "shots": 1,
        "goals": 1,
        "xg": 0.42,
        "passes": 4,
        "completed_passes": 3,
        "final_third_passes": 2,
        "completed_final_third_passes": 1,
        "long_passes": 2,
        "completed_long_passes": 2,
        "key_passes": 1,
        "pressures": 1,
        "tackles": 2,
        "won_tackles": 1,
        "clearances": 1,
        "blocks": 1,
        "dribbles": 2,
        "completed_dribbles": 1,
        "progressive_carries": 1,
        "dispossessed": 1,
        "dribbled_past": 1,
        "miscontrols": 1,
        "fouls_committed": 1,
        "fouls_won": 1,
    }
    assert len(card["passes"]) == 3
    assert card["receptions"] == [(20, 30)]
    assert card["recoveries"] == [(25, 30)]
    assert card["start_minute"] == 0 and card["end_minute"] == 70
    assert card["cards"] == ["Yellow Card", "Second Yellow"]
    assert card["rating"] is None


def test_minutes_use_substitutions_and_match_end_not_last_touch():
    events = [
        event("Pass", player=2, minute=62),
        event("Substitution", minute=60, substitution={"replacement": {"id": 2}}),
        event("Half End", minute=96, period=2),
    ]
    sub = build_player_card(MATCH, events, [], 2)
    assert (sub["start_minute"], sub["end_minute"]) == (60, 96)
    outgoing = build_player_card(MATCH, events, [{"player_id": 1, "starter": True}], 1)
    assert (outgoing["start_minute"], outgoing["end_minute"]) == (0, 60)
    unknown = build_player_card(MATCH, [event("Pass", minute=62)], [], 1)
    assert unknown["start_minute"] is None and unknown["end_minute"] is None


@pytest.mark.parametrize("ids", [[], [1, 1], [1, 2, 3]])
def test_invalid_card_counts_rejected_before_query(ids):
    with pytest.raises(ValueError):
        load_player_cards(1, ids)


@pytest.mark.parametrize("count", [1, 2])
def test_all_exports_preserve_artwork_and_end_with_both_credits(card, count):
    cards = [card, {**card, "player_id": 2, "player_name": "Segundo <jugador> & equipo"}][:count]
    png = render_player_cards_png(cards)
    with Image.open(BytesIO(png)) as picture:
        assert picture.size == (952 if count == 1 else 1888, 1440)
    html = player_cards_html(cards, png).decode()
    assert "data:image/png;base64," in html and html.count(STATSBOMB_CREDIT) == 1
    assert html.index('class="cards"') < html.index('class="report-closing"')
    assert FOOTER_URL in html and CONTACT_EMAIL in html
    if count == 2:
        assert "Segundo &lt;jugador&gt; &amp; equipo" in html
    with ZipFile(BytesIO(player_cards_docx(cards, png))) as archive:
        document = etree.fromstring(archive.read("word/document.xml"))
        namespace = document.nsmap
        tables = document.findall("w:body/w:tbl", namespace)
        assert STATSBOMB_CREDIT in "".join(tables[-2].itertext())
        assert CONTACT_EMAIL in "".join(tables[-1].itertext())
        assert document.find("w:body", namespace)[-2] == tables[-1]
        assert png in [archive.read(name) for name in archive.namelist() if name.startswith("word/media/")]
        assert len(document.xpath(".//w:drawing", namespaces=namespace)) == 3  # cards + two logos
    pdf = player_cards_pdf(cards, png)
    assert pdf.startswith(b"%PDF-") and len(pdf) > len(png) // 2


def _panel_app():
    from src.ui.i18n import install_streamlit_i18n
    from src.ui.player_cards_panel import render_player_cards_panel

    install_streamlit_i18n()
    render_player_cards_panel(
        1,
        [
            {"player_id": 1, "player_name": "A", "team_name": "Local"},
            {"player_id": 2, "player_name": "B", "team_name": "Local"},
            {"player_id": 3, "player_name": "C", "team_name": "Visitante"},
        ],
    )


def test_panel_selects_teammates_or_opponents_and_hides_stale_exports(monkeypatch, card):
    build = Mock(return_value={"cards": [card], "png": b"png", "html": b"<html>cards</html>"})
    monkeypatch.setattr(player_cards_panel, "_build_cards", build)
    monkeypatch.setattr(player_cards_panel, "_document", Mock(return_value=b"document"))
    app = AppTest.from_function(_panel_app).run()
    assert not app.exception and build.call_count == 0
    app.button(key="player_cards_generate").click().run()
    build.assert_called_with(1, (1,), "es")
    assert len(app.get("download_button")) == 3
    app.radio[0].set_value(2).run()
    assert len(app.get("download_button")) == 0
    app.button(key="player_cards_generate").click().run()
    build.assert_called_with(1, (1, 2), "es")
    assert len(app.get("download_button")) == 3
    app.selectbox[1].select(3).run()
    assert not app.exception and len(app.get("download_button")) == 0
    app.button(key="player_cards_generate").click().run()
    build.assert_called_with(1, (1, 3), "es")
    app.selectbox[0].select(3).run()
    assert app.selectbox[1].value != 3
    assert not app.exception
    st.cache_data.clear()
