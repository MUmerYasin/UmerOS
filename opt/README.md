# UmerOS /opt Package Management System

This directory contains the implementation of the Linux Filesystem Hierarchy compliant `/opt` directory structure for UmerOS.

## Overview

According to the Linux Filesystem Hierarchy Standard (FHS), `/opt` is reserved for all the software and add-on packages that are not part of the default installation. This implementation provides:

- Complete `/opt` directory structure management
- Package installation and removal functionality
- Integration with `/etc/opt` (configuration) and `/var/opt` (variable data)
- Environment variable and PATH management
- Service management for packages
- Sample installation scripts for common packages

## Directory Structure

```
/opt/
├── __init__.py          # Package initialization
├── manager.py           # Main package management interface
├── package.py           # Package class and management
├── config.py            # Configuration management
├── integration.py       # Integration modules
├── installers/          # Sample installation scripts
│   ├── __init__.py
│   ├── sample_app.py
│   ├── web_server.py
│   ├── database.py
│   └── development.py
└── README.md            # This file
```

## FHS Compliance

This implementation follows the Linux Filesystem Hierarchy Standard:

- `/opt` - Static package data
- `/etc/opt` - Host-specific configuration files
- `/var/opt` - Variable data for packages

## Usage

### Basic Package Management

```python
from opt import OptManager, OptPackage

# Initialize manager
manager = OptManager()

# Install a package
result = manager.install(
    "myapp",
    version="1.0.0",
    description="My Application",
    binaries=["/path/to/binary"],
    config={"setting": "value"}
)

# Remove a package
result = manager.remove("myapp")

# List all packages
packages = manager.list()

# Get package info
info = manager.get("myapp")
```

### Package Structure

When a package is installed, the following structure is created:

```
/opt/<package>/
├── bin/          # Executable binaries
├── lib/          # Library files
├── include/      # Header files
├── doc/          # Documentation
├── info/         # GNU Info documentation
├── man/          # Manual pages
└── src/          # Source code
```

### Installation Scripts

The `installers/` directory contains ready-to-use installation scripts:

```bash
# Install sample application
python opt/installers/sample_app.py

# Install web server
python opt/installers/web_server.py

# Install database server
python opt/installers/database.py

# Install development tools
python opt/installers/development.py
```

### Environment Integration

```python
from opt.integration import OptEnvironment

# Set up environment for a package
env = OptEnvironment()
env_vars = env.setup_package_environment("myapp")

# Discover and set up all packages
environments = env.setup_all_packages()
```

### Service Management

```python
from opt.integration import OptServiceManager

# Discover services
services = OptServiceManager().discover_services()

# Control a service
service_manager = OptServiceManager()
service_manager.start_service("myservice")
service_manager.stop_service("myservice")
service_manager.restart_service("myservice")
```

## Example: Installing a Custom Package

```python
from opt import OptManager

# Create manager
manager = OptManager()

# Install a custom package
result = manager.install(
    "mycustomapp",
    version="2.0.0",
    description="A custom application",
    binaries=["/path/to/myapp"],
    libraries=["/path/to/libmyapp.so"],
    documents=["/path/to/README.md"],
    config={
        "port": 8080,
        "debug": False,
        "log_level": "INFO"
    }
)

print(f"Installation {'successful' if result['success'] else 'failed'}")
print(f"Package path: {result['paths']['package']}")
```

## Example: Creating a Package Manually

```python
from opt.package import OptPackage

# Create a package
package = OptPackage("mypackage", provider="mycompany")

# Install binaries
package.install_binary("/path/to/binary", "myapp")

# Install libraries
package.install_library("/path/to/library.so", "libmyapp.so")

# Install documentation
package.install_documentation("/path/to/README.md")

# Create a launcher script
launcher = package.create_launcher_script(
    "myapp",
    "python3",
    ["-m", "myapp"]
)

# Verify integrity
integrity = package.verify_integrity()
print(f"Integrity: {integrity}")
```

## Configuration

Configuration files are stored in `/etc/opt/<package>/`:

```python
from opt.config import OptConfig

# Initialize config manager
config = OptConfig()

# Install configuration
config.install_config("mypackage", {
    "version": "1.0.0",
    "settings": {"debug": False}
})

# Get configuration
settings = config.get_config("mypackage")
```

## Variable Data

Variable data is stored in `/var/opt/<package>/`:

```python
from opt.config import OptIntegration

# Initialize integration manager
integration = OptIntegration()

# Setup package integration
integration.setup_integration("mypackage")

# Get package paths
paths = integration.get_package_paths("mypackage")
print(f"Data path: {paths['var']}")
```

## API Reference

### OptManager

- `install(name, provider, version, description, binaries, libraries, documents, config)` - Install a package
- `remove(name, provider)` - Remove a package
- `update(name, provider, version, config)` - Update a package
- `get(name, provider)` - Get package information
- `list()` - List all packages
- `verify(name, provider)` - Verify package integrity
- `get_stats()` - Get /opt statistics
- `create_package_structure(name, provider)` - Create package structure
- `install_binary_to_package(package_name, source_path, provider, target_name)` - Install binary

### OptPackage

- `install_binary(source_path, target_name)` - Install a binary
- `install_library(source_path, target_name)` - Install a library
- `install_documentation(source_path, target_name)` - Install documentation
- `install_man_page(source_path, section)` - Install man page
- `create_launcher_script(script_name, command, args)` - Create launcher script
- `create_wrapper_script(script_name, target_binary, environment, pre_args, post_args)` - Create wrapper script
- `remove()` - Remove package
- `exists()` - Check if package exists
- `get_installed_files()` - Get installed files
- `verify_integrity()` - Verify package integrity

### OptConfig

- `install_config(package_name, config_data, config_file)` - Install configuration
- `get_config(package_name, config_file)` - Get configuration
- `remove_config(package_name)` - Remove configuration
- `list_configs()` - List all configs
- `validate_config(package_name, schema)` - Validate configuration

### OptIntegration

- `install_package(package_name, provider)` - Install package structure
- `setup_integration(package_name, provider)` - Setup integration
- `get_package_paths(package_name, provider)` - Get package paths
- `remove_package(package_name, provider)` - Remove package
- `list_packages()` - List all packages

## Integration with /etc/opt and /var/opt

The FHS requires that:

1. **/opt** - Contains static package data
2. **/etc/opt** - Contains host-specific configuration files
3. **/var/opt** - Contains variable data for packages

This implementation manages all three directories and ensures proper integration between them.

## Testing

Run the demo scripts to test the implementation:

```bash
# Test the package manager
python opt/manager.py

# Test the package class
python opt/package.py

# Test the configuration manager
python opt/config.py

# Test the integration module
python opt/integration.py

# Test sample application installation
python opt/installers/sample_app.py
```

## License

This implementation is provided as-is for use in UmerOS.

## Author

UmerOS Development Team
