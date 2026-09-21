"""The video switch is read from the environment like every other setting."""
from __future__ import annotations

import importlib

import pytest


@pytest.mark.parametrize(
    "raw, expected",
    [("true", True), ("1", True), ("false", False), ("", False)],
)
def test_record_video_reads_the_environment(monkeypatch, raw, expected) -> None:
    monkeypatch.setenv("RECORD_VIDEO", raw)
    import toolshop.config as config

    importlib.reload(config)
    assert config.settings.record_video is expected


def test_record_video_is_off_by_default(monkeypatch) -> None:
    monkeypatch.delenv("RECORD_VIDEO", raising=False)
    import toolshop.config as config

    importlib.reload(config)
    assert config.settings.record_video is False
