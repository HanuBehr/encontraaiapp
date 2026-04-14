from __future__ import annotations

from pathlib import Path


STREAMLIT_APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"


def _streamlit_source() -> str:
    return STREAMLIT_APP.read_text(encoding="utf-8")


def test_streamlit_discovery_defaults_are_garin_facing() -> None:
    source = _streamlit_source()

    for legacy_term in [
        "oficina mecânica",
        "auto elétrica",
        "auto center",
        "desmanche",
        "autopeças",
        "manutenção de computadores",
        "baterias",
    ]:
        assert legacy_term not in source

    for garin_term in [
        "materiais de construção",
        "loja de tintas",
        "indústria química",
        "marketplace / loja virtual",
    ]:
        assert garin_term in source


def test_streamlit_copy_uses_garin_workspace_language() -> None:
    source = _streamlit_source()

    assert "LeadFlow Workspace" not in source
    assert "Garin prospecting workspace" in source
    assert "Suggested Garin segments and subsegments" in source
    assert "Provider category" in source


def test_streamlit_enrich_action_does_not_mutate_queue_widget_key() -> None:
    source = _streamlit_source()
    enrich_block = source.split('if st.button("Find more public contact info"', maxsplit=1)[1].split(
        'st.caption("Open keeps',
        maxsplit=1,
    )[0]

    assert 'st.session_state["lead_queue_selected_id"]' not in enrich_block
    assert 'st.session_state["selected_lead_id"] = selected_lead_id' in enrich_block


def test_streamlit_duplicate_preview_uses_flat_readable_rows() -> None:
    source = _streamlit_source()
    preview_block = source.split('if st.button("Preview possible duplicates in shown leads"', maxsplit=1)[1].split(
        'if st.button("Mark duplicates in shown leads"',
        maxsplit=1,
    )[0]

    assert "_duplicate_preview_rows(preview)" in preview_block
    assert 'item.model_dump(mode="json") for item in preview.items' not in preview_block
    for column_name in [
        "lead_a_name",
        "lead_b_name",
        "city",
        "phone_a",
        "phone_b",
        "whatsapp_a",
        "whatsapp_b",
        "reasons",
    ]:
        assert f'"{column_name}"' in source


def test_streamlit_surfaces_lead_quality_filters_and_columns() -> None:
    source = _streamlit_source()

    assert "COMPANY_SIZE_FIT_FILTER_OPTIONS" in source
    assert "TRADE_TYPE_FILTER_OPTIONS" in source
    assert '"Target fit"' in source
    assert '"Trade type"' in source
    assert '"Fit"' in source
    assert '"Trade"' in source
    assert "_render_quality_section(lead)" in source
