from __future__ import annotations

import runpy
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "debug_cnpja_resolution.py"
SCRIPT_GLOBALS = runpy.run_path(str(SCRIPT_PATH))
render_value = SCRIPT_GLOBALS["render_value"]


def test_render_value_handles_empty_values() -> None:
    assert render_value(None) == "-"
    assert render_value("") == "-"


def test_render_value_handles_dict_and_list_without_crashing() -> None:
    assert render_value({"alpha": 1, "items": [1, 2]}) == '{"alpha":1,"items":[1,2]}'
    assert render_value(["a", {"b": True}]) == '["a",{"b":true}]'


def test_render_value_redacts_sensitive_keys() -> None:
    rendered = render_value(
        {
            "Authorization": "secret-value",
            "nested": {"api_key": "abc123", "token_value": "xyz"},
            "safe": "ok",
        }
    )
    assert "[redacted]" in rendered
    assert "secret-value" not in rendered
    assert "abc123" not in rendered
    assert "xyz" not in rendered
    assert '"safe":"ok"' in rendered
