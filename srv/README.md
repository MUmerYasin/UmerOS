# UmerOS `/srv` — Site-Specific Service Data Hierarchy


---

## 1. Overview & Purpose

The `/srv` directory contains **site-specific data which is served by this system**.

### Key Principles from:
1. **Centralized Service Data:** Provides a unified location for data files served by system services (WWW, FTP, Git, Rsync, TFTP, Samba, NFS).
2. **Single-Tree Organization:** Services requiring a single tree for read-only data, writable data, and scripts (such as CGI scripts) can be cleanly housed together:
   ```
   /srv/<service_name>/
       ├── html/ (or htdocs/ or data/)
       ├── cgi-bin/ (or scripts/)
       ├── uploads/ (or incoming/)
       └── conf/ (site configuration)
   ```
3. **Data Isolation:**
   - Personal user data belongs in `/home/<user>`, not in `/srv`.
   - Internal non-served application state belongs in `/var/lib`, not in `/srv`.
   - Binaries belong in `/usr/bin` or `/usr/sbin`, not in `/srv`.
4. **Administrative Protection:** Operating systems and distribution utilities must **not** delete or clobber files in `/srv` without explicit administrator consent.

---

## 2. Directory Structure & Organization Schemes

UmerOS `/srv` supports multiple organization schemes per FHS:

* **Protocol-Based (Default):**
  - `/srv/www` — Web sites, HTML document roots, CGI scripts, uploads
  - `/srv/ftp` — Anonymous archive (`/pub`), upload drop-box (`/incoming`)
  - `/srv/git` — Bare repositories, hooks, description files
  - `/srv/rsync` — Rsync mirrors, shares, rsyncd module configs
  - `/srv/tftp` — PXE boot images, kernel/initrd, boot menus
  - `/srv/nfs` & `/srv/samba` — Network file exports and shares
* **Domain / Virtual Host-Based:**
  - `/srv/example.com/www`
  - `/srv/api.org/v1`
* **Department-Based:**
  - `/srv/physics/www`
  - `/srv/compsci/cvs`

---

## 3. Architecture & Modules

| Module | Description |
|---|---|
| `fhs.py` | FHS 2.3/3.0 & TLDP rules, protocol directories, prohibited path validation, path classification. |
| `hierarchy.py` | Physical directory provisioning, single-tree service layouts, skeleton bootstrapping, space stats. |
| `service.py` | Dataclasses for `ServiceRecord`, `ServiceConfig`, `ServiceStatus`, `ServiceAccessMode`. |
| `permissions.py` | Security profiles (WWW, FTP, Git, Rsync, TFTP), sticky-bit verification, permission auditing. |
| `protocols.py` | Protocol handlers for WWW (vhosts/test server), FTP, Git (bare repos), Rsync, TFTP, Samba/NFS. |
| `backup.py` | Automated snapshots, tar.gz/zip archiving, metadata manifests, backup restoration. |
| `manager.py` | Master `SrvManager` coordinator, JSON registry persistence, automatic directory discovery. |
| `cli.py` | Command-line tool `srv_ctl` / `python -m srv.cli`. |
| `test_srv.py` | Comprehensive test suite verifying all modules and FHS compliance. |

---

## 4. Python API Usage

```python
from srv import SrvManager, StandardProtocol, OrganizationScheme

# Initialize manager
mgr = SrvManager()

# Bootstrap standard skeletons (www, ftp, git, rsync, tftp, nfs, samba)
mgr.hierarchy.bootstrap()

# Create a new web service with single-tree structure
service = mgr.create_service(
    name="myportal",
    protocol=StandardProtocol.WWW,
    scheme=OrganizationScheme.BY_PROTOCOL,
)
print(f"Service created at: {service.base_path}")
print(f"Data root: {service.data_path}")
print(f"CGI root: {service.cgi_path}")

# Run FHS & Security Audit
audit_report = mgr.audit_all()
print(f"Audit Health: {'OK' if audit_report['is_healthy'] else 'ISSUES'}")

# Create backup archive
archive = mgr.backup_manager.create_backup(service.base_path, archive_format="tar.gz")
print(f"Backup created: {archive}")
```

---

## 5. Command-Line Interface (`srv_ctl`)

```bash
# List all registered services
python -m srv.cli list

# Show detailed configuration of a service
python -m srv.cli show www

# Bootstrap standard FHS skeletons
python -m srv.cli bootstrap

# Create a new domain-based service
python -m srv.cli create mysite --protocol www --scheme by_domain --domain example.com

# Run full FHS compliance and permission security audit
python -m srv.cli audit

# View storage summary and statistics
python -m srv.cli summary

# Create compressed backup of a service
python -m srv.cli backup www --format tar.gz

# Restore service from backup
python -m srv.cli restore /path/to/backup.tar.gz --overwrite
```

---

## 6. Testing

Run the built-in test suite:
```bash
python srv/test_srv.py
```
Or via pytest:
```bash
pytest tests/test_srv.py
```
