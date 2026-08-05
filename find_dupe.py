import re
with open('bin/bin_manager.py') as f:
    content = f.read()
    registered = re.findall(r'"(\w+)":\s*\(', content)
# Find duplicates
from collections import Counter
c = Counter(registered)
dupes = {k: v for k, v in c.items() if v > 1}
print("Duplicates:", dupes)
