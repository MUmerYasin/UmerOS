"""Add 54 new entries to bin_manager.py COMMAND_REGISTRY."""
import re

# Read current bin_manager.py
with open("bin/bin_manager.py") as f:
    content = f.read()

# Find the end of the current COMMAND_REGISTRY dict
# Look for the last entry before the closing brace
# The registry ends with something like: }
# Let's find the last "}" that closes the dict

# First, let's find where the dict ends by looking for the closing pattern
# The dict entries end before the "}" that's followed by a newline and comment

# Find all entries
entries = re.findall(r'"([a-z][a-z0-9_-]*)":\s*\("([^"]+)",\s*"([^"]+)"\)', content)
existing_keys = set(k for k, _, _ in entries)
print(f"Existing registry entries: {len(existing_keys)}")

# Find the last entry line
last_entry_match = re.search(r'(\s+"[a-z][a-z0-9_-]*":\s*\("[^"]+",\s*"[^"]+"\),?\n)(\s*\}\n)', content)
if last_entry_match:
    insert_pos = last_entry_match.end(1)
    print(f"Found insertion point at position {insert_pos}")
else:
    # Try another pattern
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if line.strip().startswith('"') and 'Command' in line and ':' in line:
            last_entry_line = i
    print(f"Last entry line: {last_entry_line}")

# Build the new entries with correct class names
new_entries = {
    # usr_sbin_cmds.py
    "crond": ("usr_sbin_cmds", "CRONDCommand"),
    "cron": ("usr_sbin_cmds", "CRONCommand"),
    "atd": ("usr_sbin_cmds", "ATDCommand"),
    "crontab-daemon": ("usr_sbin_cmds", "CRONTABDaemonCommand"),
    "xinetd": ("usr_sbin_cmds", "XINETDCommand"),
    "chronyd": ("usr_sbin_cmds", "CHRONYCommand"),
    "ntpd": ("usr_sbin_cmds", "NTDPCommand"),
    "sshd": ("usr_sbin_cmds", "SSHDCommand"),
    "httpd": ("usr_sbin_cmds", "HTTPDCommand"),
    "nginx": ("usr_sbin_cmds", "NGINXCommand"),
    "mysqld": ("usr_sbin_cmds", "MYSQLDCommand"),
    "postgresql": ("usr_sbin_cmds", "POSTGRESQLCommand"),
    "redis": ("usr_sbin_cmds", "REDISCommand"),
    "syslogd": ("usr_sbin_cmds", "SYSLOGDCommand"),
    "klogd": ("usr_sbin_cmds", "KLOGDCommand"),
    "rsyslogd": ("usr_sbin_cmds", "RSYSLOGDCommand"),
    "systemd-journald": ("usr_sbin_cmds", "SYSTEMDJOURNALCommand"),
    "monitord": ("usr_sbin_cmds", "MONITORDCommand"),
    "dpkg-daemon": ("usr_sbin_cmds", "DPKGDAEMONCommand"),
    "aptd": ("usr_sbin_cmds", "APTDCommand"),
    "yum-daemon": ("usr_sbin_cmds", "YUMDAEMONCommand"),
    "dnfd": ("usr_sbin_cmds", "DNFDCommand"),
    "snapd": ("usr_sbin_cmds", "SNAPPYDCommand"),
    "slapd": ("usr_sbin_cmds", "LDAPDAEMONCommand"),
    "nss-daemon": ("usr_sbin_cmds", "NSSDAEMONCommand"),
    "systemd": ("usr_sbin_cmds", "SYSTEMDCommand"),
    "udevd": ("usr_sbin_cmds", "UDEVDDCommand"),
    "libvirtd": ("usr_sbin_cmds", "LIBVIRTDCommand"),
    "dockerd": ("usr_sbin_cmds", "DOCKERDCommand"),
    "kubelet": ("usr_sbin_cmds", "KUBELETCommand"),
    "containerd": ("usr_sbin_cmds", "CONTAINERDCommand"),
    # usr_share.py
    "pager": ("usr_share", "PAGERCommand"),
    "nroff": ("usr_share", "NROFFCommand"),
    "troff": ("usr_share", "TROFFCommand"),
    "groff": ("usr_share", "GROFFCommand"),
    "col": ("usr_share", "COLCommand"),
    "colrm": ("usr_share", "COLRMCommand"),
    "info": ("usr_share", "INFCommand"),
    "tzselect": ("usr_share", "TZSELECTCommand"),
    "zic": ("usr_share", "ZICCommand"),
    "zdump": ("usr_share", "ZDUMPCommand"),
    "localedef": ("usr_share", "LOCALEDEFCOMMAND"),
    "howto": ("usr_share", "HOWTOCommand"),
    "faq": ("usr_share", "FAQCommand"),
    # usr_local.py
    "local-bin": ("usr_local", "LOCALBINCommand"),
    "local-etc": ("usr_local", "LOCALETCCommand"),
    "local-lib": ("usr_local", "LOCALLIBCommand"),
    "local-share": ("usr_local", "LOCALSHARECommand"),
    "local-sbin": ("usr_local", "LOCALSBINCommand"),
    "local-include": ("usr_local", "LOCALINCLUDECommand"),
    "local-man": ("usr_local", "LOCALMANCommand"),
    "local-doc": ("usr_local", "LOCALDOCCommand"),
    "local-src": ("usr_local", "LOCALSRCCommand"),
}

# Filter out existing entries
to_add = {k: v for k, v in new_entries.items() if k not in existing_keys}
print(f"New entries to add: {len(to_add)}")

# Build new entry lines
new_lines = []
for key in sorted(to_add.keys()):
    module, cls = to_add[key]
    new_lines.append(f'    "{key}": ("{module}", "{cls}"),')

# Find the insertion point - the line before the closing }
lines = content.split('\n')
insert_line = None
for i, line in enumerate(lines):
    if line.strip() == '}' and i > 0 and 'Command' in lines[i-1]:
        insert_line = i
        break

if insert_line is None:
    print("ERROR: Could not find insertion point")
    exit(1)

print(f"Inserting before line {insert_line + 1}")

# Insert new entries
for j, new_line in enumerate(new_lines):
    lines.insert(insert_line + j, new_line)

# Write back
new_content = '\n'.join(lines)
with open("bin/bin_manager.py", 'w') as f:
    f.write(new_content)

print(f"Added {len(new_lines)} entries to COMMAND_REGISTRY")
print(f"New total: {len(existing_keys) + len(to_add)} entries")
