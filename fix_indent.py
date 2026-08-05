import re

path = 'bin/usr_cmds.py'
with open(path, 'r') as f:
    content = f.read()

# Find all class definitions followed by 8-space docstrings and fix to 4-space
# Pattern: class Foo:\n        """...""" -> class Foo:\n    """..."""
fixed = re.sub(r'(class \w+:)\n        (\'\'\'|\"\"\")', r'\1\n    \2', content)

with open(path, 'w') as f:
    f.write(fixed)

print("Fixed all 8-space docstrings to 4-space")
