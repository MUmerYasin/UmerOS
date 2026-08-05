import re

with open('bin/bin_manager.py') as f:
    content = f.read()
    registered = set(re.findall(r'"(\w+)":\s*\(', content))

with open('bin/usr_cmds.py') as f:
    ucs = set(re.findall(r'class (\w+Command):', f.read()))

cmd_names = set()
for c in ucs:
    cmd = c.replace('Command', '').lower()
    cmd_names.add(cmd)

skip = cmd_names & registered
print("SKIP (already registered):")
for s in sorted(skip):
    print(f'    "{s}"')
print(f"Count: {len(skip)}")

add = cmd_names - registered
print("\nADD (new commands):")
for a in sorted(add):
    cls = a.replace('Command', '') + 'Command'
    print(f'    "{a}": ("usr_cmds", "{cls}"),')
print(f"Count: {len(add)}")
