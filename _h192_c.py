"""H192 applier C: OptConfig provider scoping + manager forwarding."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load(p: Path):
    raw = p.read_bytes().decode("utf-8")
    crlf = "\r\n" in raw
    return raw.replace("\r\n", "\n"), crlf


def save(p: Path, text: str, crlf: bool) -> None:
    p.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))


def sub(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    assert n == 1, f"{label}: expected 1 occurrence, found {n}"
    return text.replace(old, new)


# ══════════════════════════════════════════════════════════════════════════
# opt/config.py - provider-scoped configuration paths
# ══════════════════════════════════════════════════════════════════════════
p = ROOT / "opt" / "config.py"
text, crlf = load(p)

# get_config_path gains provider
old = '''    def get_config_path(self, package_name: str, config_file: str = "") -> Path:
        """
        Get the path for a package's configuration file.
        
        Args:
            package_name: Name of the package
            config_file: Optional configuration file name
            
        Returns:
            Path to the configuration file
            
        Raises:
            PathTraversalError: if package_name/config_file would escape the
                /etc/opt root (fail-closed; callers catch and refuse).
        """
        # Contain the package dir and (optional) nested config file
        # inside /etc/opt. A name like "../../etc/passwd" is refused.
        base = safe_child(self.etc_opt_root, package_name)
        if config_file:
            return safe_join(base, config_file)
        return base
'''
new = '''    def get_config_path(self, package_name: str, config_file: str = "",
                        provider: str = "") -> Path:
        """
        Get the path for a package's configuration file.
        
        Args:
            package_name: Name of the package
            config_file: Optional configuration file name
            provider: Optional provider name (config lands in
                /etc/opt/<provider>/<package>, matching where the package
                itself is installed under /opt)
            
        Returns:
            Path to the configuration file
            
        Raises:
            PathTraversalError: if package_name/config_file would escape the
                /etc/opt root (fail-closed; callers catch and refuse).
        """
        # Contain the package dir and (optional) nested config file
        # inside /etc/opt. A name like "../../etc/passwd" is refused.
        if provider:
            base = safe_child(safe_child(self.etc_opt_root, provider), package_name)
        else:
            base = safe_child(self.etc_opt_root, package_name)
        if config_file:
            return safe_join(base, config_file)
        return base
'''
text = sub(text, old, new, "config get_config_path")

# install_config gains provider
old = '''    def install_config(self, package_name: str, config_data: Dict[str, Any], 
                       config_file: str = "config.json") -> Path:
        """
        Install configuration for a package.
        
        Args:
            package_name: Name of the package
            config_data: Dictionary containing configuration data
            config_file: Name of the configuration file
            
        Returns:
            Path to the installed configuration file
            
        Raises:
            ValueError: if the resolved config path would escape /etc/opt
                (path-traversal refusal).
        """
        # [FIX H184] privileged write under /etc/opt -> require fs.admin.
        gate.require(CAP_FS_ADMIN)

        try:
            config_path = self.get_config_path(package_name, config_file)
'''
new = '''    def install_config(self, package_name: str, config_data: Dict[str, Any], 
                       config_file: str = "config.json",
                       provider: str = "") -> Path:
        """
        Install configuration for a package.
        
        Args:
            package_name: Name of the package
            config_data: Dictionary containing configuration data
            config_file: Name of the configuration file
            provider: Optional provider name (see get_config_path)
            
        Returns:
            Path to the installed configuration file
            
        Raises:
            ValueError: if the resolved config path would escape /etc/opt
                (path-traversal refusal).
        """
        # [FIX H184] privileged write under /etc/opt -> require fs.admin.
        gate.require(CAP_FS_ADMIN)

        try:
            config_path = self.get_config_path(package_name, config_file, provider)
'''
text = sub(text, old, new, "config install_config")

# get_config gains provider
old = '''    def get_config(self, package_name: str, config_file: str = "config.json") -> Optional[Dict[str, Any]]:
        """
        Get configuration for a package.
        
        Args:
            package_name: Name of the package
            config_file: Name of the configuration file
            
        Returns:
            Configuration dictionary or None if not found
        """
        try:
            config_path = self.get_config_path(package_name, config_file)
'''
new = '''    def get_config(self, package_name: str, config_file: str = "config.json",
                   provider: str = "") -> Optional[Dict[str, Any]]:
        """
        Get configuration for a package.
        
        Args:
            package_name: Name of the package
            config_file: Name of the configuration file
            provider: Optional provider name (see get_config_path)
            
        Returns:
            Configuration dictionary or None if not found
        """
        try:
            config_path = self.get_config_path(package_name, config_file, provider)
'''
text = sub(text, old, new, "config get_config")

# remove_config gains provider
old = '''    def remove_config(self, package_name: str) -> bool:
        """
        Remove all configuration for a package.
        
        Args:
            package_name: Name of the package
            
        Returns:
            True if removal was successful
        """
        # [FIX H184] privileged rmtree/unlink under /etc/opt -> require fs.admin.
        gate.require(CAP_FS_ADMIN)

        try:
            config_path = safe_child(self.etc_opt_root, package_name)
'''
new = '''    def remove_config(self, package_name: str, provider: str = "") -> bool:
        """
        Remove all configuration for a package.
        
        Args:
            package_name: Name of the package
            provider: Optional provider name (see get_config_path)
            
        Returns:
            True if removal was successful
        """
        # [FIX H184] privileged rmtree/unlink under /etc/opt -> require fs.admin.
        gate.require(CAP_FS_ADMIN)

        try:
            if provider:
                config_path = safe_child(
                    safe_child(self.etc_opt_root, provider), package_name
                )
            else:
                config_path = safe_child(self.etc_opt_root, package_name)
'''
text = sub(text, old, new, "config remove_config")

# validate_config gains provider
old = '''    def validate_config(self, package_name: str, schema: Optional[Dict[str, Any]] = None) -> bool:
        """
        Validate package configuration.
        
        Args:
            package_name: Name of the package
            schema: Optional JSON schema for validation
            
        Returns:
            True if configuration is valid
        """
        config = self.get_config(package_name)
'''
new = '''    def validate_config(self, package_name: str,
                        schema: Optional[Dict[str, Any]] = None,
                        provider: str = "") -> bool:
        """
        Validate package configuration.
        
        Args:
            package_name: Name of the package
            schema: Optional JSON schema for validation
            provider: Optional provider name (see get_config_path)
            
        Returns:
            True if configuration is valid
        """
        config = self.get_config(package_name, provider=provider)
'''
text = sub(text, old, new, "config validate_config")

# selftest: pin the provider-scoped config path
old = '''        # 1  install + read back a configuration
        path = cfg.install_config("demo", {"version": "1.0.0", "debug": False})
        # safe_child resolves paths while tempfile hands back Windows 8.3
        # short names, so compare resolved forms (same trick as the H189 tests)
        assert Path(str(path)).resolve() == (etc / "demo" / "config.json").resolve(), path
        assert cfg.get_config("demo") == {"version": "1.0.0", "debug": False}
'''
new = '''        # 1  install + read back a configuration
        path = cfg.install_config("demo", {"version": "1.0.0", "debug": False})
        # safe_child resolves paths while tempfile hands back Windows 8.3
        # short names, so compare resolved forms (same trick as the H189 tests)
        assert Path(str(path)).resolve() == (etc / "demo" / "config.json").resolve(), path
        assert cfg.get_config("demo") == {"version": "1.0.0", "debug": False}

        # 1b  provider-scoped config lands next to the package it belongs to
        prov_path = cfg.install_config(
            "demo", {"version": "2.0.0"}, provider="acme"
        )
        assert Path(str(prov_path)).resolve() == (
            etc / "acme" / "demo" / "config.json"
        ).resolve(), prov_path
        assert cfg.get_config("demo", provider="acme") == {"version": "2.0.0"}
        assert cfg.get_config("demo") == {"version": "1.0.0"}
        assert cfg.remove_config("demo", provider="acme") is True
        assert cfg.get_config("demo", provider="acme") is None
        print("  [PASS] provider-scoped configuration paths")
'''
text = sub(text, old, new, "config selftest provider case")
save(p, text, crlf)
print("opt/config.py OK")

# ══════════════════════════════════════════════════════════════════════════
# opt/manager.py - forward the provider into the config layer
# ══════════════════════════════════════════════════════════════════════════
p = ROOT / "opt" / "manager.py"
text, crlf = load(p)

old = '''            # Store configuration
            if config:
                config_path = self.config_manager.install_config(name, config)
                result["paths"]["config"] = str(config_path)
'''
new = '''            # Store configuration (provider-scoped, so it lands next to
            # the package it belongs to instead of a flat /etc/opt/<name>)
            if config:
                config_path = self.config_manager.install_config(
                    name, config, provider=provider
                )
                result["paths"]["config"] = str(config_path)
'''
text = sub(text, old, new, "manager install config provider")

old = '''            # Update configuration if provided
            if config:
                config_path = self.config_manager.install_config(name, config)
                db[package_key]["paths"]["config"] = str(config_path)
'''
new = '''            # Update configuration if provided
            if config:
                config_path = self.config_manager.install_config(
                    name, config, provider=provider
                )
                db[package_key]["paths"]["config"] = str(config_path)
'''
text = sub(text, old, new, "manager update config provider")
save(p, text, crlf)
print("opt/manager.py OK")
