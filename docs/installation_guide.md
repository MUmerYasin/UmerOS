# Umer OS — Installation Guide

## Quick Reference

| Platform | Method | Status |
|---|---|---|
| Desktop / Laptop (x86_64) | Python installer | ✅ TODAY |
| Raspberry Pi 4 / 5 (ARM64) | dd image to SD | ✅ TODAY |
| NVIDIA Jetson (ARM64) | dd image to SD | ✅ TODAY |
| Android phone (AArch64) | fastboot + TWRP | 🔬 EXPERIMENTAL |
| Smart TV (Android base) | ADB sideload | 🔬 EXPERIMENTAL |
| QEMU (development) | qemu-system-x86_64 | ✅ TODAY |
| iPhone / iPad | Not supported | ❌ BLOCKED |

## Step-by-Step: Desktop / Laptop

### Prerequisites
- Python 3.10+ installed
- 512 MB free RAM, 500 MB free disk
- Terminal / Command Prompt access

### Installation Steps
```bash
# 1. Extract archive
unzip UmerOS.zip && cd UmerOS

# 2. Install dependencies
pip install numpy cryptography

# 3. Run test suite (should show 305 tests OK)
python -m unittest discover -s tests -v

# 4. Run installer (interactive — follow prompts)
python installer/installer.py

# 5. Reboot
```

### What the Installer Does
1. Displays full EULA (you must type I AGREE exactly)
2. Detects your hardware
3. Creates backup of boot configuration
4. Copies Umer OS files to /opt/umer_os/
5. Installs boot entry
6. Writes first-boot configuration

## Step-by-Step: QEMU (Development / Testing)

```bash
# Build QEMU disk image
bash build/build.sh --output dist/umeros.img

# Launch in QEMU (4 GB RAM, 4 CPUs)
bash build/qemu_launcher.sh
# OR manually:
qemu-system-x86_64 -m 4G -smp 4 \
  -drive file=dist/umeros.img,format=qcow2 \
  -enable-kvm -vga virtio -net user
```

## Step-by-Step: Android (Experimental)

```bash
# 1. Enable Developer Options on your Android device
#    Settings → About Phone → tap Build Number 7 times

# 2. Enable USB Debugging
#    Settings → Developer Options → USB Debugging → ON

# 3. Unlock bootloader (VOIDS WARRANTY)
fastboot oem unlock

# 4. Flash TWRP custom recovery
fastboot flash recovery twrp-<device>.img
fastboot reboot recovery

# 5. Sideload Umer OS from TWRP menu
adb sideload umeros-arm64.zip

# 6. Reboot
```

## Rollback / Uninstall

```bash
# Automated rollback (uses pre-install backup)
python installer/rollback_tools/restore_bootloader.py
python installer/rollback_tools/restore_partitions.py

# Manual: remove install directory
sudo rm -rf /opt/umer_os
```

## Troubleshooting

| Problem | Solution |
|---|---|
| `python: command not found` | Install Python 3.10+ from python.org |
| `No module named numpy` | `pip install numpy` |
| `305 tests FAIL` | Check Python version: `python --version` |
| QEMU: `KVM not available` | Remove `-enable-kvm` flag |
| Android: `fastboot not found` | `sudo apt install android-tools-fastboot` |
