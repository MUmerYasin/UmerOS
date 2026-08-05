"""Check for conflicts between new files and COMMAND_REGISTRY."""
import re

# Get COMMAND_REGISTRY keys from bin_manager.py
with open("bin/bin_manager.py") as f:
    content = f.read()
registry_keys = set(re.findall(r'"([a-z][a-z0-9_-]*)":', content))

print("Registry has", len(registry_keys), "entries")

# Parse helper
def get_names(filepath, mapping=None):
    with open(filepath) as f:
        content = f.read()
    classes = re.findall(r'class (\w+Command)\(Command\):', content)
    names = []
    for c in classes:
        name = c.replace('Command', '').lower()
        if mapping and name in mapping:
            name = mapping[name]
        names.append(name)
    return names

# usr_sbin_cmds.py
sbin_map = {
    'inetdc': 'inetd', 'ntdp': 'ntpd', 'systemdjournald': 'systemd-journald',
    'slapd': 'slapd', 'nssd': 'nss-daemon', 'dpkgd': 'dpkg-daemon',
    'aptd': 'aptd', 'yumd': 'yum-daemon', 'dnfd': 'dnfd',
    'snapd': 'snapd', 'systemd': 'systemd', 'udevd': 'udevd',
}
sbin_names = get_names("bin/usr_sbin_cmds.py", sbin_map)
print("\n=== usr_sbin_cmds.py:", len(sbin_names), "classes ===")
sbin_conflicts = [n for n in sbin_names if n in registry_keys]
if sbin_conflicts:
    print("CONFLICTS:", sbin_conflicts)
else:
    print("No conflicts")

# usr_share.py
share_map = {'etcconfig': 'etc-config', 'bashdefaults': 'bash-defaults'}
share_names = get_names("bin/usr_share.py", share_map)
print("\n=== usr_share.py:", len(share_names), "classes ===")
share_conflicts = [n for n in share_names if n in registry_keys]
if share_conflicts:
    print("CONFLICTS:", share_conflicts)
else:
    print("No conflicts")

# usr_local.py
local_map = {
    'localbin': 'local-bin', 'localetc': 'local-etc', 'locallib': 'local-lib',
    'localshare': 'local-share', 'localsbin': 'local-sbin',
    'localinclude': 'local-include', 'localman': 'local-man',
    'localdoc': 'local-doc', 'localsrc': 'local-src',
}
local_names = get_names("bin/usr_local.py", local_map)
print("\n=== usr_local.py:", len(local_names), "classes ===")
local_conflicts = [n for n in local_names if n in registry_keys]
if local_conflicts:
    print("CONFLICTS:", local_conflicts)
else:
    print("No conflicts")

# Print new entries to add
print("\n=== NEW ENTRIES TO ADD ===")
total = 0
for name in sbin_names:
    if name not in registry_keys:
        cls = name.replace("-", "_").title().replace(" ", "") + "Command"
        print(f'    "{name}": ("usr_sbin_cmds", "{cls}"),')
        total += 1

for name in share_names:
    if name not in registry_keys:
        cls = name.replace("-", "_").title().replace(" ", "") + "Command"
        print(f'    "{name}": ("usr_share", "{cls}"),')
        total += 1

for name in local_names:
    if name not in registry_keys:
        cls = name.replace("-", "_").title().replace(" ", "") + "Command"
        print(f'    "{name}": ("usr_local", "{cls}"),')
        total += 1

print(f"\nTotal new entries: {total}")
