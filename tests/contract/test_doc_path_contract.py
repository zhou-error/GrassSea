"""文档输出路径契约测试（审计 S3-1）

背景：resolve_output("/etc/passwd") 曾被静默改写成 <outputs>/etc/passwd 并返回成功，
用户以为写到了 /etc，实际落在数据目录 —— 静默行为差异。
"""

from __future__ import annotations

import pytest

from tools.doc._common import DocPathError, resolve_output


@pytest.mark.parametrize("bad", [
    "/etc/passwd",
    "C:\\Windows\\evil.docx",
    "D:/evil.docx",
])
def test_absolute_paths_rejected(apply_settings, tmp_path, bad):
    apply_settings(DATA_DIR=str(tmp_path))
    with pytest.raises(DocPathError) as exc:
        resolve_output(bad)
    assert "绝对路径" in str(exc.value)


def test_traversal_still_rejected(apply_settings, tmp_path):
    apply_settings(DATA_DIR=str(tmp_path))
    with pytest.raises(DocPathError):
        resolve_output("../../evil.docx")


def test_relative_path_ok(apply_settings, tmp_path):
    apply_settings(DATA_DIR=str(tmp_path))
    target = resolve_output("报告/分析.docx")
    assert target.name == "分析.docx"
    assert str(tmp_path) in str(target)
