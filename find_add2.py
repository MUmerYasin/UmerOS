import re

with open('bin/bin_manager.py') as f:
    content = f.read()
    registered = set(re.findall(r'"(\w+)":\s*\(', content))

with open('bin/usr_cmds.py') as f:
    # Find both class name and command name
    pairs = re.findall(r'class (\w+Command):', f.read())

cmd_names = {}
for cls in pairs:
    cmd = cls.replace('Command', '').lower()
    cmd_names[cmd] = cls

add = {k: v for k, v in cmd_names.items() if k not in registered}

for cmd, cls in sorted(add.items()):
    print(f'    "{cmd}": ("usr_cmds", "{cls}"),')
print(f"\nCount: {len(add)}")
