"""pin that provider tokens never have to travel on the command line.

The row said ``quantum/cli.py`` ``backends``/``execute``/``jobs`` accept
``--token``/``-t``, so tokens end up in ``ps`` output, ``/proc/<pid>/cmdline``
and shell history.

Fix (session 209): added secure channels and a single resolver.

Preference order (explicit flags beat the environment; secure channels beat
the deprecated one):

1. ``--token-file PATH``  — read from a credential file
2. ``--token-stdin``      — read one line from stdin
3. ``--token-prompt``     — ``getpass`` prompt, input not echoed
4. ``--token``            — DEPRECATED, emits a warning
5. ``UMEROS_*_TOKEN``-style environment variable

The token value is never printed or logged.
"""

from __future__ import annotations

import ast
import io
import os
import sys
from pathlib import Path

import pytest

CLI_PATH = Path(__file__).resolve().parent.parent / "quantum" / "cli.py"

SUBCOMMANDS = ("backends", "execute", "jobs")
TOKEN_ATTRS = ("token", "token_file", "token_stdin", "token_prompt")


def _src() -> str:
    return CLI_PATH.read_text(encoding="utf-8")


def _cli():
    root = str(CLI_PATH.parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    from quantum import cli

    return cli


# ------------------------------------------------------------------ parser surface


class TestParserSurface:
    """Every provider subcommand must offer the secure channels."""

    @pytest.mark.parametrize("subcommand", SUBCOMMANDS)
    def test_secure_channels_exist(self, subcommand: str) -> None:
        cli = _cli()
        ns = cli.build_parser().parse_args([subcommand, "--provider", "ibm"])
        for attr in TOKEN_ATTRS:
            assert hasattr(ns, attr), f"{subcommand} missing --{attr.replace('_', '-')}"

    @pytest.mark.parametrize("subcommand", SUBCOMMANDS)
    def test_token_marked_deprecated(self, subcommand: str) -> None:
        cli = _cli()
        parser = cli.build_parser()
        action = next(
            a
            for a in parser._subparsers._group_actions[0].choices[subcommand]._actions
            if "--token" in a.option_strings
        )
        assert "DEPRECATED" in (action.help or ""), (
            f"{subcommand}: --token help must flag it as deprecated"
        )

    def test_defaults_are_falsey(self) -> None:
        cli = _cli()
        ns = cli.build_parser().parse_args(["backends", "--provider", "ibm"])
        assert ns.token is None
        assert ns.token_file is None
        assert ns.token_stdin is False
        assert ns.token_prompt is False


# ------------------------------------------------------------------ resolution


class TestTokenResolution:
    """The resolver must prefer secure channels and never echo secrets."""

    def test_token_file_wins(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        cli = _cli()
        monkeypatch.setenv("UMEROS_IBM_TOKEN", "env-secret")
        cred = tmp_path / "tok"
        cred.write_text("file-secret\n", encoding="utf-8")
        ns = cli.build_parser().parse_args(
            ["backends", "--provider", "ibm", "--token-file", str(cred)]
        )
        assert cli._resolve_provider_token(ns, "ibm") == "file-secret"

    def test_token_file_beats_legacy_argv(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cli = _cli()
        monkeypatch.delenv("UMEROS_IBM_TOKEN", raising=False)
        cred = tmp_path / "tok"
        cred.write_text("file-secret", encoding="utf-8")
        ns = cli.build_parser().parse_args(
            ["backends", "--provider", "ibm", "--token", "argv", "--token-file", str(cred)]
        )
        assert cli._resolve_provider_token(ns, "ibm") == "file-secret"

    def test_stdin_channel(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cli = _cli()
        monkeypatch.delenv("UMEROS_IONQ_API_KEY", raising=False)
        ns = cli.build_parser().parse_args(
            ["backends", "--provider", "ionq", "--token-stdin"]
        )
        monkeypatch.setattr(sys, "stdin", io.StringIO("stdin-secret\n"))
        assert cli._resolve_provider_token(ns, "ionq") == "stdin-secret"

    def test_prompt_channel(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cli = _cli()
        monkeypatch.delenv("UMEROS_IONQ_API_KEY", raising=False)
        monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": "prompt-secret")
        ns = cli.build_parser().parse_args(
            ["backends", "--provider", "ionq", "--token-prompt"]
        )
        assert cli._resolve_provider_token(ns, "ionq") == "prompt-secret"

    def test_env_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cli = _cli()
        monkeypatch.setenv("UMEROS_IBM_TOKEN", "env-secret")
        ns = cli.build_parser().parse_args(["backends", "--provider", "ibm"])
        assert cli._resolve_provider_token(ns, "ibm") == "env-secret"

    def test_legacy_token_still_works_and_warns(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        cli = _cli()
        monkeypatch.delenv("UMEROS_IBM_TOKEN", raising=False)
        ns = cli.build_parser().parse_args(
            ["backends", "--provider", "ibm", "--token", "argv-secret"]
        )
        value = cli._resolve_provider_token(ns, "ibm")
        err = capsys.readouterr().err
        assert value == "argv-secret", "backward compatibility must be kept"
        assert "Warning" in err
        assert "argv-secret" not in err, "the token value must never be echoed"

    def test_explicit_flag_beats_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cli = _cli()
        monkeypatch.setenv("UMEROS_IBM_TOKEN", "env-secret")
        ns = cli.build_parser().parse_args(
            ["backends", "--provider", "ibm", "--token", "argv-secret"]
        )
        assert cli._resolve_provider_token(ns, "ibm") == "argv-secret", (
            "an explicit flag must win over the environment"
        )

    def test_returns_none_when_nothing_supplied(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cli = _cli()
        monkeypatch.delenv("UMEROS_BRAKET_ACCESS_KEY", raising=False)
        ns = cli.build_parser().parse_args(["backends", "--provider", "braket"])
        assert cli._resolve_provider_token(ns, "braket") is None

    def test_missing_token_file_is_graceful(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        cli = _cli()
        monkeypatch.delenv("UMEROS_IBM_TOKEN", raising=False)
        ns = cli.build_parser().parse_args(
            ["backends", "--provider", "ibm", "--token-file", str(tmp_path / "nope")]
        )
        assert cli._resolve_provider_token(ns, "ibm") is None
        assert "Error" in capsys.readouterr().err

    def test_unknown_provider_is_safe(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cli = _cli()
        ns = cli.build_parser().parse_args(["backends", "--provider", "nope"])
        assert cli._resolve_provider_token(ns, "nope") is None


# ------------------------------------------------------------------ env map


class TestProviderEnvMap:
    """Every supported provider must have an environment variable."""

    @pytest.mark.parametrize(
        "provider",
        ["ibm", "ibm_quantum", "ionq", "braket", "aws_braket", "rigetti", "qcs"],
    )
    def test_provider_has_env_var(self, provider: str) -> None:
        cli = _cli()
        assert provider in cli._PROVIDER_TOKEN_ENV
        assert cli._PROVIDER_TOKEN_ENV[provider].startswith("UMEROS_")

    def test_env_names_match_auth_module(self) -> None:
        """The CLI must agree with the credential layer's variable names."""
        cli = _cli()
        from quantum.cloud import auth

        for provider, env_name in cli._PROVIDER_TOKEN_ENV.items():
            if provider in auth._ENV_KEY_MAP:
                assert auth._ENV_KEY_MAP[provider] == env_name, (
                    f"{provider}: CLI and auth disagree on the env var name"
                )


# ------------------------------------------------------------------ source invariants


class TestSourceInvariants:
    """No call site may hand a raw argv token to a provider."""

    def test_no_raw_args_token(self) -> None:
        src = _src()
        assert "api_token=args.token" not in src, "raw argv token still used"
        assert "api_key=args.token" not in src, "raw argv token still used"

    def test_resolver_used_at_every_site(self) -> None:
        src = _src()
        uses = src.count("_resolve_provider_token(args, provider_name)")
        assert uses == 6, f"expected 6 resolver call sites, found {uses}"

    def test_docstring_documents_credentials(self) -> None:
        doc = ast.get_docstring(ast.parse(_src()))
        assert doc is not None
        lowered = doc.lower()
        assert "--token-file" in doc
        assert "shell history" in lowered
        assert "environment variables" in lowered

    def test_section1_trailers(self) -> None:
        src = _src()
        assert "Author:  Umer OS Project" in src
        assert "License: GPL-3.0 (GNU General Public License v3)" in src

    def test_warning_does_not_interpolate_token(self) -> None:
        """The deprecation warning must not embed the secret."""
        tree = ast.parse(_src())
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_resolve_provider_token":
                for sub in ast.walk(node):
                    if isinstance(sub, ast.JoinedStr):
                        rendered = "".join(
                            v.value for v in sub.values if isinstance(v, ast.Constant)
                        )
                        if "Warning" in rendered:
                            assert "legacy" not in rendered, (
                                "warning interpolates the token value"
                            )
