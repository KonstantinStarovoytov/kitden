"""How Kitden was installed: uv tool, Homebrew, or something Kitden cannot update."""

import subprocess

from kitden.update.install import MANUAL_COMMAND, Install, detect, installed_version


def test_uv_tool_install(tmp_path):
    prefix = tmp_path / "tools" / "kitden"
    (prefix / "bin").mkdir(parents=True)
    (prefix / "uv-receipt.toml").write_text("")
    got = detect(prefix, which=lambda n: "/usr/bin/uv" if n == "uv" else None)
    assert got == Install(
        "uv", prefix / "bin" / "kitden", ("/usr/bin/uv", "tool", "upgrade", "kitden")
    )


def test_brew_install_uses_the_opt_link(tmp_path):
    prefix = tmp_path / "Cellar" / "kitden" / "0.7.2" / "libexec"
    prefix.mkdir(parents=True)
    got = detect(prefix, which=lambda n: None)
    assert got is not None
    assert got.method == "brew"
    assert got.launcher == tmp_path / "opt" / "kitden" / "bin" / "kitden"
    assert got.command == (str(tmp_path / "bin" / "brew"), "upgrade", "kitden")


def test_brew_install_reached_through_the_opt_link(tmp_path):
    # Python can run from opt/kitden/libexec, a link to the version's folder in the Cellar.
    cellar = tmp_path / "Cellar" / "kitden" / "0.7.2"
    (cellar / "libexec").mkdir(parents=True)
    (tmp_path / "opt").mkdir()
    (tmp_path / "opt" / "kitden").symlink_to(cellar)
    got = detect(tmp_path / "opt" / "kitden" / "libexec", which=lambda n: None)
    assert got is not None
    assert got.method == "brew"
    assert got.launcher == tmp_path.resolve() / "opt" / "kitden" / "bin" / "kitden"
    assert got.command == (str(tmp_path.resolve() / "bin" / "brew"), "upgrade", "kitden")


def test_uvx_pip_or_source_get_no_install(tmp_path):
    assert detect(tmp_path / "cache" / "archive-v0" / "abc", which=lambda n: "/usr/bin/uv") is None


def test_another_cellar_formula_is_not_kitden(tmp_path):
    prefix = tmp_path / "Cellar" / "other" / "1.0" / "libexec"
    assert detect(prefix, which=lambda n: None) is None


def test_uv_tool_without_uv_on_path_gets_none(tmp_path):
    prefix = tmp_path / "tools" / "kitden"
    prefix.mkdir(parents=True)
    (prefix / "uv-receipt.toml").write_text("")
    assert detect(prefix, which=lambda n: None) is None


def _install(tmp_path):
    return Install("uv", tmp_path / "bin" / "kitden", ("uv", "tool", "upgrade", "kitden"))


def test_installed_version_reads_the_launcher(tmp_path):
    seen = {}

    def run(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["timeout"] = kwargs.get("timeout")
        return subprocess.CompletedProcess(cmd, 0, stdout="kitden 0.7.3\n", stderr="")

    install = _install(tmp_path)
    assert installed_version(install, run=run) == "0.7.3"
    assert seen["cmd"] == [str(install.launcher), "--version"]
    assert seen["timeout"] == 10


def test_installed_version_is_none_on_any_error(tmp_path):
    def missing(cmd, **kwargs):
        raise FileNotFoundError(cmd[0])

    def slow(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 10)

    def failed(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="boom")

    def odd(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout="hello", stderr="")

    install = _install(tmp_path)
    for run in (missing, slow, failed, odd):
        assert installed_version(install, run=run) is None


def test_manual_command_names_each_way():
    assert MANUAL_COMMAND == {
        "uv": "uv tool upgrade kitden",
        "brew": "brew upgrade kitden",
        None: "uv tool install --python 3.13 kitden",  # the README line: uvx, pip, source
    }
