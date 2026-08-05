import re
with open('bin/bin_manager.py') as f:
    content = f.read()
    registered = set(re.findall(r'"(\w+)":\s*\(', content))
print('Total commands:', len(registered))
