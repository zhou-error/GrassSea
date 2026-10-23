"""排版模板契约测试

背景：模板合并曾是浅合并，用户只写 page.margin_cm.top 就把
bottom/left/right 整块覆盖掉，页边距静默变成 0。
"""

from __future__ import annotations

import tempfile
from pathlib import Path


def test_partial_override_preserves_siblings(apply_settings, tmp_path):
    data_dir = tmp_path
    (data_dir / "templates").mkdir()
    (data_dir / "templates" / "partial.yaml").write_text(
        "page:\n  margin_cm:\n    top: 1.5\n", encoding="utf-8"
    )
    apply_settings(DATA_DIR=str(data_dir))

    from shared.utils.docx_render import DEFAULT_STYLE, _apply_template

    style = _apply_template(DEFAULT_STYLE, "partial")
    margins = style["page"]["margin_cm"]
    assert margins["top"] == 1.5
    # 未提到的兄弟键必须保留默认值
    assert margins["bottom"] == 2.54
    assert margins["left"] == 3.17
    assert margins["right"] == 3.17


def test_missing_template_falls_back_to_defaults(apply_settings, tmp_path):
    apply_settings(DATA_DIR=str(tmp_path))
    from shared.utils.docx_render import DEFAULT_STYLE, _apply_template

    style = _apply_template(DEFAULT_STYLE, "does-not-exist")
    assert style["body"]["font"]
    assert style["page"]["margin_cm"]["left"] == 3.17


def test_repo_default_template_exists():
    from pathlib import Path as P

    assert P("templates/report.yaml").exists()
