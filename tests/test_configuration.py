import pytest

from utils import config


def test_env_file_preserves_process_overrides(tmp_path, monkeypatch):
    monkeypatch.setenv("M3U_REVIEW_OVERRIDE", "process")
    monkeypatch.delenv("M3U_REVIEW_NEW", raising=False)
    path = tmp_path / ".env"
    path.write_text(
        '# comment\nM3U_REVIEW_OVERRIDE=file\nM3U_REVIEW_NEW="hello"\n', encoding="utf-8"
    )
    config.load_env(path)
    import os

    assert os.environ["M3U_REVIEW_OVERRIDE"] == "process"
    assert os.environ["M3U_REVIEW_NEW"] == "hello"
    monkeypatch.delenv("M3U_REVIEW_NEW")


def test_env_rejects_invalid_boolean(monkeypatch):
    monkeypatch.setenv("M3U_REVIEW_BOOLEAN", "flase")
    with pytest.raises(ValueError):
        config.env_bool("M3U_REVIEW_BOOLEAN", True)


def test_launcher_check_reports_ready_without_starting_server(capsys):
    from utils.launcher import main

    assert main(["--check"]) == 0
    assert "Hazır" in capsys.readouterr().out


def test_entrypoint_and_assets_are_found_outside_project_directory(tmp_path, monkeypatch):
    from utils.launcher import app_path

    monkeypatch.chdir(tmp_path)
    path = app_path()
    assert path.name == "app.py"
    assert path.is_file()
    assert (path.parent / "static" / "styles.css").is_file()
