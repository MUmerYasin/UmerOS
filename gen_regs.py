import re

with open('bin/usr_commands.py') as f:
    uc = set(re.findall(r'class (\w+Command):', f.read()))

with open('bin/usr_cmds.py') as f:
    ucs = set(re.findall(r'class (\w+Command):', f.read()))

unique = sorted(ucs - uc)
for c in unique:
    cmd = c.replace('Command', '').lower()
    print(f'    "{cmd}": ("usr_cmds", "{c}"),')
