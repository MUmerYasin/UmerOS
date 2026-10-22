"""H192 applier H: normalize the two new opt __main__.py files to CRLF."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent

for rel in ("opt/__main__.py", "opt/installers/__main__.py"):
    p = ROOT / rel
    raw = p.read_bytes().decode("utf-8")
    assert "\r\n" not in raw, f"{rel}: already CRLF?"
    text = raw.replace("\r\n", "\n").replace("\n", "\r\n")
    p.write_bytes(text.encode("utf-8"))
    # verify: no lone LFs
    back = p.read_bytes().decode("utf-8")
    assert back.count("\n") == back.count("\r\n"), f"{rel}: mixed endings"
    print(f"{rel} -> CRLF ({back.count(chr(13) + chr(10))} lines)")
