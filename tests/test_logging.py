"""Tests for file logging, which is what makes a detached service diagnosable."""

import logging
from pathlib import Path

import pytest

import bot


@pytest.fixture(autouse=True)
def _restore_logging():
    """Undo handler changes so tests don't leak logging state into each other."""
    root = logging.getLogger()
    saved = root.handlers[:]
    saved_level = root.level
    yield
    root.handlers[:] = saved
    root.setLevel(saved_level)


class TestResolveLogFile:
    def test_none_by_default(self, monkeypatch):
        monkeypatch.delenv("LOG_FILE", raising=False)
        assert bot.resolve_log_file([]) is None

    def test_space_separated_form(self, monkeypatch):
        monkeypatch.delenv("LOG_FILE", raising=False)
        assert bot.resolve_log_file(["--log-file", "bot.log"]) == "bot.log"

    def test_equals_form(self, monkeypatch):
        monkeypatch.delenv("LOG_FILE", raising=False)
        assert bot.resolve_log_file(["--log-file=bot.log"]) == "bot.log"

    def test_env_var_fallback(self, monkeypatch):
        monkeypatch.setenv("LOG_FILE", "/var/log/bot.log")
        assert bot.resolve_log_file([]) == "/var/log/bot.log"

    def test_flag_beats_env_var(self, monkeypatch):
        monkeypatch.setenv("LOG_FILE", "/from/env.log")
        assert bot.resolve_log_file(["--log-file", "chosen.log"]) == "chosen.log"

    def test_missing_value_raises(self, monkeypatch):
        monkeypatch.delenv("LOG_FILE", raising=False)
        with pytest.raises(ValueError):
            bot.resolve_log_file(["--log-file"])

    def test_flag_followed_by_another_flag_raises(self, monkeypatch):
        # "--log-file --setup" should complain, not silently use "--setup".
        monkeypatch.delenv("LOG_FILE", raising=False)
        with pytest.raises(ValueError):
            bot.resolve_log_file(["--log-file", "--setup"])

    def test_empty_equals_form_raises(self, monkeypatch):
        monkeypatch.delenv("LOG_FILE", raising=False)
        with pytest.raises(ValueError):
            bot.resolve_log_file(["--log-file="])


class TestConfigureLogging:
    def test_console_only_when_no_path(self):
        bot.configure_logging(None)
        handlers = logging.getLogger().handlers
        assert not any(isinstance(h, bot.RotatingFileHandler) for h in handlers)

    def test_writes_to_the_requested_file(self, tmp_path):
        target = tmp_path / "bot.log"
        bot.configure_logging(str(target))
        logging.getLogger("tickerbot").info("hello from the test")
        for handler in logging.getLogger().handlers:
            handler.flush()
        assert target.is_file()
        assert "hello from the test" in target.read_text(encoding="utf-8")

    def test_rotation_matches_the_docker_policy(self, tmp_path):
        bot.configure_logging(str(tmp_path / "bot.log"))
        file_handlers = [
            h
            for h in logging.getLogger().handlers
            if isinstance(h, bot.RotatingFileHandler)
        ]
        assert len(file_handlers) == 1
        handler = file_handlers[0]
        assert handler.maxBytes == 10 * 1024 * 1024
        assert handler.backupCount == 3

    def test_creates_missing_parent_directories(self, tmp_path):
        target = tmp_path / "nested" / "deeper" / "bot.log"
        bot.configure_logging(str(target))
        logging.getLogger("tickerbot").info("x")
        assert target.is_file()

    def test_no_duplicate_handlers_on_repeat_calls(self, tmp_path):
        target = str(tmp_path / "bot.log")
        bot.configure_logging(target)
        bot.configure_logging(target)
        file_handlers = [
            h
            for h in logging.getLogger().handlers
            if isinstance(h, bot.RotatingFileHandler)
        ]
        assert len(file_handlers) == 1


class TestServiceTemplates:
    """The unit files can't be registered in CI, so at least assert the
    directives that make them supervise correctly are present and spelled
    right."""

    @property
    def service_dir(self) -> Path:
        return Path(__file__).resolve().parent.parent / "packaging" / "service"

    def test_systemd_unit_restarts_and_throttles(self):
        text = (self.service_dir / "autoticker-bot.service").read_text()
        assert "Restart=always" in text
        assert "RestartSec=5" in text
        # Without a start limit a bad token restarts forever.
        assert "StartLimitBurst=5" in text
        assert "StartLimitIntervalSec=300" in text
        assert "WantedBy=default.target" in text

    def test_systemd_start_limits_are_in_the_unit_section(self):
        # systemd 229+ rejects these in [Service]; a misplaced directive would
        # silently lose the crash-loop guard.
        text = (self.service_dir / "autoticker-bot.service").read_text()
        unit_block = text.split("[Unit]", 1)[1].split("[Service]", 1)[0]
        assert "StartLimitBurst" in unit_block
        assert "StartLimitIntervalSec" in unit_block

    def test_systemd_unit_passes_a_log_file(self):
        text = (self.service_dir / "autoticker-bot.service").read_text()
        assert "--log-file" in text
        assert "WorkingDirectory=" in text

    def test_launchd_plist_is_valid_xml_and_supervises(self):
        import plistlib

        raw = (self.service_dir / "com.autoticker.bot.plist").read_bytes()
        data = plistlib.loads(raw)
        assert data["Label"] == "com.autoticker.bot"
        assert data["RunAtLoad"] is True
        assert data["KeepAlive"] is True
        assert data["ThrottleInterval"] == 30
        assert "--log-file" in data["ProgramArguments"]

    def test_windows_task_avoids_the_three_day_timeout(self):
        text = (self.service_dir / "windows-task.ps1").read_text()
        # Task Scheduler stops tasks after 3 days unless the limit is zero.
        assert "ExecutionTimeLimit ([TimeSpan]::Zero)" in text
        assert "-RestartCount 3" in text
        assert "-AtLogOn" in text
        assert "--log-file" in text

    def test_placeholders_are_consistent(self):
        for name in ("autoticker-bot.service", "com.autoticker.bot.plist"):
            text = (self.service_dir / name).read_text()
            assert "__INSTALL_DIR__" in text, name
