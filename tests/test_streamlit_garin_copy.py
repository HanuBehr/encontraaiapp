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
