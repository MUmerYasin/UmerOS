"""H222 applier -- stop requiring provider tokens on the command line.

Assert-first: every anchor's occurrence count is verified before writing.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

TARGET = Path("quantum/cli.py")
src = TARGET.read_text(encoding="utf-8")
original = src


def sub(old: str, new: str, label: str, expect: int = 1) -> None:
    global src
    count = src.count(old)
    if count != expect:
        print(f"ABORT [{label}]: expected {expect} occurrence(s), found {count}")
        sys.exit(1)
    src = src.replace(old, new)


# ---------------------------------------------------------------- 1. docstring
sub(
    '''Usage:
    python -m quantum.cli <command> [options]
    python quantum/cli.py <command> [options]
"""''',
    '''Usage:
    python -m quantum.cli <command> [options]
    python quantum/cli.py <command> [options]

Credentials
-----------
Provider tokens are **not** meant to be passed on the command line, where they
end up in ``ps`` output, ``/proc/<pid>/cmdline`` and shell history.  Use one of:

    --token-file PATH     read the token from a credential file
    --token-stdin         read one line from stdin
    --token-prompt        interactive prompt (input not echoed)
    UMEROS_IBM_TOKEN / UMEROS_IONQ_API_KEY / UMEROS_BRAKET_ACCESS_KEY /
    UMEROS_RIGETTI_API_KEY                        environment variables

``--token`` still works for backward compatibility but is deprecated and emits
a warning.  The token value is never printed.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""''',
    "docstring",
)

# ---------------------------------------------------------------- 2. imports
sub(
    "import argparse\nimport json\nimport sys\nimport time\n",
    "import argparse\nimport getpass\nimport json\nimport os\nimport sys\nimport time\nfrom pathlib import Path\n",
    "imports",
)

# ---------------------------------------------------------------- 3. token resolver
sub(
    '''def cmd_backends(args: argparse.Namespace) -> int:
    """List backends for a provider."""''',
    '''#: Environment variables that can carry a provider token, keyed by provider.
_PROVIDER_TOKEN_ENV = {
    "ibm": "UMEROS_IBM_TOKEN",
    "ibm_quantum": "UMEROS_IBM_TOKEN",
    "ionq": "UMEROS_IONQ_API_KEY",
    "braket": "UMEROS_BRAKET_ACCESS_KEY",
    "aws_braket": "UMEROS_BRAKET_ACCESS_KEY",
    "rigetti": "UMEROS_RIGETTI_API_KEY",
    "qcs": "UMEROS_RIGETTI_API_KEY",
}


def _resolve_provider_token(
    args: argparse.Namespace, provider_name: str
) -> Optional[str]:
    """Resolve a provider token without putting it on the command line.

    Preference order:

    1. ``--token-file``   -- read the token from a credential file
    2. ``--token-stdin``  -- read one line from stdin
    3. ``--token-prompt`` -- interactive :func:`getpass` prompt (no echo)
    4. the provider's environment variable (see ``_PROVIDER_TOKEN_ENV``)
    5. ``--token``        -- DEPRECATED: argv is visible in ``ps``,
       ``/proc/<pid>/cmdline`` and shell history; accepted with a warning

    The token value is never printed or logged.
    """
    token_file = getattr(args, "token_file", None)
    if token_file:
        try:
            value = Path(token_file).read_text(encoding="utf-8").strip()
        except OSError as exc:
            print(
                f"Error: cannot read token file {token_file}: {exc}",
                file=sys.stderr,
            )
            return None
        return value or None

    if getattr(args, "token_stdin", False):
        return sys.stdin.readline().strip() or None

    if getattr(args, "token_prompt", False):
        return getpass.getpass(f"{provider_name} API token: ").strip() or None

    env_name = _PROVIDER_TOKEN_ENV.get(provider_name)
    if env_name:
        value = os.environ.get(env_name)
        if value:
            return value.strip()

    legacy = getattr(args, "token", None)
    if legacy:
        print(
            "Warning: --token exposes the credential in process listings and "
            "shell history; prefer --token-file, --token-stdin, --token-prompt "
            f"or {env_name or 'the provider environment variable'}.",
            file=sys.stderr,
        )
        return legacy

    return None


def cmd_backends(args: argparse.Namespace) -> int:
    """List backends for a provider."""''',
    "token resolver",
)

# ---------------------------------------------------------------- 4. call sites
sub(
    "            p = IBMQuantumProvider(api_token=args.token)",
    "            p = IBMQuantumProvider(\n                api_token=_resolve_provider_token(args, provider_name))",
    "ibm call sites",
    expect=3,
)

sub(
    "            p = IonQProvider(api_key=args.token)",
    "            p = IonQProvider(\n                api_key=_resolve_provider_token(args, provider_name))",
    "ionq call sites",
    expect=3,
)

# ---------------------------------------------------------------- 5. subparser args
TOKEN_ARGS = '''    {var}.add_argument("--token", "-t", help="API token (DEPRECATED: visible in ps and shell history)")
    {var}.add_argument("--token-file", help="Read the API token from this file")
    {var}.add_argument("--token-stdin", action="store_true", help="Read the API token from stdin")
    {var}.add_argument("--token-prompt", action="store_true", help="Prompt for the API token (no echo)")
'''

sub(
    '    p_backends.add_argument("--token", "-t", help="API token")\n',
    TOKEN_ARGS.format(var="p_backends"),
    "backends args",
)

sub(
    '    p_exec.add_argument("--token", "-t", help="API token")\n',
    TOKEN_ARGS.format(var="p_exec"),
    "execute args",
)

sub(
    '    p_jobs.add_argument("--token", "-t", help="API token")\n',
    TOKEN_ARGS.format(var="p_jobs"),
    "jobs args",
)

# ---------------------------------------------------------------- verify
ast.parse(src)
assert src.count("args.token)") == 0, "a raw args.token call site survived"
assert "_resolve_provider_token(args, provider_name)" in src
assert src != original

TARGET.write_text(src, encoding="utf-8")
print("OK: quantum/cli.py no longer requires tokens on argv.")
