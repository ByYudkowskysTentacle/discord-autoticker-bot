"""Tests for the command-line entry points that exit before touching Discord."""

import bot


class TestVersionFlag:
    def test_prints_version_and_license_notice(self, capsys):
        bot.main(["--version"])
        out = capsys.readouterr().out
        assert bot.__version__ in out
        assert "AGPL-3.0" in out


class TestHelpFlag:
    def test_lists_every_flag(self, capsys):
        bot.main(["--help"])
        out = capsys.readouterr().out
        for flag in ("--setup", "--version", "--license", "--help"):
            assert flag in out


class TestLicenseFlag:
    """The bare Windows .exe ships no sidecar files, so the program itself has
    to be able to produce the license text."""

    def test_prints_the_actual_agpl_text(self, capsys):
        bot.main(["--license"])
        out = capsys.readouterr().out
        assert "GNU AFFERO GENERAL PUBLIC LICENSE" in out
        # Section 13 is the network-use clause that makes this AGPL, not GPL.
        assert "13. Remote Network Interaction" in out

    def test_license_text_is_not_the_fallback(self):
        # Guards against the LICENSE file going missing from a build: the
        # fallback string would silently replace the real terms.
        assert "could not be read" not in bot.license_text()

    def test_bundled_path_resolves_next_to_the_module(self):
        assert bot.bundled_path("LICENSE").is_file()
