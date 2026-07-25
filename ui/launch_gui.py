#!/usr/bin/env python3
"""
UmerOS UI Launcher
Script to launch the Flutter-based graphical user interface (GUI) shell.
Expects the Flutter project to be located at 'ui/flutter_ui'.
Requires Flutter SDK to be installed and accessible from PATH.
"""
import os
import sys
import subprocess
import logging
import time
from pathlib import Path # Use pathlib for robust path manipulation

# Configure logging for this module
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def find_flutter_exe_or_script():
    """
    Uses 'where' to find the flutter command (executable or script) and returns its full path.
    Handles cases where 'where' returns a path without the .bat/.cmd extension.
    """
    try:
        result = subprocess.run(['where', 'flutter'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
        if result.returncode == 0:
            flutter_cmd_path_str = result.stdout.strip().split('\n')[0] # Get the first path found
            flutter_cmd_path = Path(flutter_cmd_path_str)
            
            # Check if the path returned by 'where' exists as-is (e.g., if it's an .exe)
            if flutter_cmd_path.exists():
                logger.info(f"Flutter command found: {flutter_cmd_path_str}")
                # Determine if it's likely a script by checking the extension
                if flutter_cmd_path.suffix.lower() in ['.bat', '.cmd', '.ps1']:
                    logger.info(f"Detected as script ({flutter_cmd_path.suffix}). Will invoke via shell.")
                    return str(flutter_cmd_path) # Return the path as found
                else:
                    logger.info(f"Detected as executable ({flutter_cmd_path.suffix}).")
                    return str(flutter_cmd_path) # Return the path as found
            
            # If the path doesn't exist as-is, it might be missing the extension (e.g., 'flutter' instead of 'flutter.bat')
            else:
                # Common script extensions on Windows
                possible_extensions = ['.bat', '.cmd', '.ps1']
                for ext in possible_extensions:
                    extended_path = flutter_cmd_path.with_suffix(ext)
                    if extended_path.exists():
                        logger.info(f"Flutter command found (with extension): {extended_path}")
                        logger.info(f"Detected as script ({extended_path.suffix}). Will invoke via shell.")
                        return str(extended_path) # Return the path with the correct extension
                
                # If none of the extended paths exist, log an error
                logger.error(f"'where flutter' returned a path that does not exist: {flutter_cmd_path_str}")
                logger.error("Checked potential script extensions, none found.")
                return None
                
        else:
            logger.error("'where flutter' returned no results.")
            return None
    except FileNotFoundError:
        logger.error("The 'where' command itself failed. Are you on Windows?")
        return None
    except subprocess.TimeoutExpired:
        logger.error("Finding Flutter path timed out.")
        return None
    except Exception as e:
        logger.error(f"Unexpected error while finding Flutter path: {e}")
        return None

def check_flutter_installed():
    """
    Check if the 'flutter' command is available using the full path found by 'where'.
    Handles batch scripts (.bat, .cmd) by invoking them via 'cmd /c'.
    """
    flutter_cmd_path = find_flutter_exe_or_script()
    if not flutter_cmd_path:
        logger.error("Flutter SDK not found via 'where' command.")
        logger.error("Please ensure Flutter is installed and 'flutter' command is in your PATH environment variable.")
        logger.error("Hint: After adding Flutter to PATH, you must open a *NEW* terminal window to see the changes reflected in Python subprocesses.")
        return False

    # Determine if the found command is a script that needs shell invocation
    flutter_path_obj = Path(flutter_cmd_path)
    is_script = flutter_path_obj.suffix.lower() in ['.bat', '.cmd', '.ps1']

    try:
        if is_script:
            # Use 'cmd /c' to run the batch script
            cmd_list = ['cmd', '/c', flutter_cmd_path, '--version']
            logger.info(f"Running Flutter check via shell: {' '.join(cmd_list)}")
        else:
            # Run the executable directly
            cmd_list = [flutter_cmd_path, '--version']
            logger.info(f"Running Flutter check directly: {' '.join(cmd_list)}")

        result = subprocess.run(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
        if result.returncode == 0:
            logger.info("Flutter SDK found and verified: %s", result.stdout.strip().split('\n')[0])
            return True
        else:
            logger.error(f"Flutter command at '{flutter_cmd_path}' failed with error: %s", result.stderr)
            return False
    except FileNotFoundError:
        logger.error(f"Flutter command not found or not executable at path: {flutter_cmd_path}")
        return False
    except subprocess.TimeoutExpired:
        logger.error("Flutter --version command timed out.")
        return False
    except Exception as e:
        logger.error(f"Unexpected error while checking Flutter: {e}")
        return False

def launch_flutter_desktop(flutter_project_path):
    """Attempt to launch the Flutter app as a desktop application."""
    logger.info("Attempting to launch Flutter GUI for Desktop...")
    flutter_cmd_path = find_flutter_exe_or_script()
    if not flutter_cmd_path:
        logger.error("Cannot launch GUI: Flutter command path not found.")
        return -1

    flutter_path_obj = Path(flutter_cmd_path)
    is_script = flutter_path_obj.suffix.lower() in ['.bat', '.cmd', '.ps1']

    try:
        if is_script:
            cmd_list = ['cmd', '/c', flutter_cmd_path, 'run', '--release']
        else:
            cmd_list = [flutter_cmd_path, 'run', '--release']

        logger.info(f"Executing command: {' '.join(cmd_list)} in directory: {flutter_project_path}")

        process = subprocess.Popen(
            cmd_list,
            cwd=flutter_project_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )

        logger.info("Flutter desktop app started. Monitoring process... (Press Ctrl+C in the kernel shell to stop the GUI)")

        stdout, stderr = process.communicate()
        if stdout:
             logger.info(f"Flutter desktop app output:\n{stdout}")
        if stderr:
             logger.warning(f"Flutter desktop app errors:\n{stderr}")

        return process.returncode

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to launch Flutter desktop app: {e}")
        logger.error(f"Command: {e.cmd}, Return Code: {e.returncode}")
        return e.returncode
    except Exception as e:
        logger.error(f"An unexpected error occurred while launching Flutter desktop: {e}")
        return -1

def launch_flutter_android(flutter_project_path):
    """Attempt to launch the Flutter app on an Android device/emulator."""
    logger.info("Attempting to launch Flutter GUI for Android...")
    flutter_cmd_path = find_flutter_exe_or_script()
    if not flutter_cmd_path:
        logger.error("Cannot launch GUI: Flutter command path not found.")
        return -1

    flutter_path_obj = Path(flutter_cmd_path)
    is_script = flutter_path_obj.suffix.lower() in ['.bat', '.cmd', '.ps1']

    try:
        # Check for connected Android devices
        check_devices_cmd = ['cmd', '/c', flutter_cmd_path, 'devices'] if is_script else [flutter_cmd_path, 'devices']
        devices_result = subprocess.run(check_devices_cmd, cwd=flutter_project_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if devices_result.returncode != 0 or 'android' not in devices_result.stdout.lower():
            logger.error("No Android device/emulator found. Please connect a device or start an emulator.")
            logger.error(f"Flutter devices output:\n{devices_result.stdout}\n{devices_result.stderr}")
            return -1

        cmd_list = ['cmd', '/c', flutter_cmd_path, 'run', '-d', 'android', '--release'] if is_script else [flutter_cmd_path, 'run', '-d', 'android', '--release']
        logger.info(f"Executing command: {' '.join(cmd_list)} in directory: {flutter_project_path}")

        process = subprocess.Popen(
            cmd_list,
            cwd=flutter_project_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )

        logger.info("Flutter Android app started. Monitoring process... (Check your device/emulator)")

        stdout, stderr = process.communicate()
        if stdout:
             logger.info(f"Flutter Android app output:\n{stdout}")
        if stderr:
             logger.warning(f"Flutter Android app errors:\n{stderr}")

        return process.returncode

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to launch Flutter Android app: {e}")
        logger.error(f"Command: {e.cmd}, Return Code: {e.returncode}")
        return e.returncode
    except Exception as e:
        logger.error(f"An unexpected error occurred while launching Flutter Android: {e}")
        return -1

def launch_flutter_ios(flutter_project_path):
    """Attempt to launch the Flutter app on an iOS simulator/device (requires macOS)."""
    logger.info("Attempting to launch Flutter GUI for iOS...")
    flutter_cmd_path = find_flutter_exe_or_script()
    if not flutter_cmd_path:
        logger.error("Cannot launch GUI: Flutter command path not found.")
        return -1

    flutter_path_obj = Path(flutter_cmd_path)
    is_script = flutter_path_obj.suffix.lower() in ['.bat', '.cmd', '.ps1']

    try:
        # Check for connected iOS devices/simulators
        check_devices_cmd = ['cmd', '/c', flutter_cmd_path, 'devices'] if is_script else [flutter_cmd_path, 'devices']
        devices_result = subprocess.run(check_devices_cmd, cwd=flutter_project_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if devices_result.returncode != 0 or 'ios' not in devices_result.stdout.lower():
            logger.error("No iOS simulator/device found. Ensure Xcode and iOS tools are installed and a simulator is running.")
            logger.error(f"Flutter devices output:\n{devices_result.stdout}\n{devices_result.stderr}")
            return -1

        # Prefer simulator if available
        device_id = None
        for line in devices_result.stdout.split('\n'):
            if 'ios' in line.lower() and 'simulator' in line.lower():
                parts = line.split()
                if parts:
                    device_id = parts[0] # Assume first word is ID
                    break
        if not device_id:
             # If no simulator, try first iOS device
             for line in devices_result.stdout.split('\n'):
                 if 'ios' in line.lower():
                     parts = line.split()
                     if parts:
                         device_id = parts[0]
                         break

        if device_id:
            cmd_list = ['cmd', '/c', flutter_cmd_path, 'run', '-d', device_id, '--release'] if is_script else [flutter_cmd_path, 'run', '-d', device_id, '--release']
        else:
            cmd_list = ['cmd', '/c', flutter_cmd_path, 'run', '-d', 'ios', '--release'] if is_script else [flutter_cmd_path, 'run', '-d', 'ios', '--release']

        logger.info(f"Executing command: {' '.join(cmd_list)} in directory: {flutter_project_path}")

        process = subprocess.Popen(
            cmd_list,
            cwd=flutter_project_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )

        logger.info("Flutter iOS app started. Monitoring process... (Check your simulator/device)")

        stdout, stderr = process.communicate()
        if stdout:
             logger.info(f"Flutter iOS app output:\n{stdout}")
        if stderr:
             logger.warning(f"Flutter iOS app errors:\n{stderr}")

        return process.returncode

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to launch Flutter iOS app: {e}")
        logger.error(f"Command: {e.cmd}, Return Code: {e.returncode}")
        return e.returncode
    except Exception as e:
        logger.error(f"An unexpected error occurred while launching Flutter iOS: {e}")
        return -1

def launch_flutter_web(flutter_project_path):
    """Attempt to launch the Flutter app in a web browser."""
    logger.info("Attempting to launch Flutter GUI for Web...")
    flutter_cmd_path = find_flutter_exe_or_script()
    if not flutter_cmd_path:
        logger.error("Cannot launch GUI: Flutter command path not found.")
        return -1

    flutter_path_obj = Path(flutter_cmd_path)
    is_script = flutter_path_obj.suffix.lower() in ['.bat', '.cmd', '.ps1']

    try:
        cmd_list = ['cmd', '/c', flutter_cmd_path, 'run', '-d', 'chrome', '--web-port=7575', '--release'] if is_script else [flutter_cmd_path, 'run', '-d', 'chrome', '--web-port=7575', '--release']

        logger.info(f"Executing command: {' '.join(cmd_list)} in directory: {flutter_project_path}")

        process = subprocess.Popen(
            cmd_list,
            cwd=flutter_project_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )

        logger.info("Flutter web app started. Monitoring process... (Check http://localhost:7575 or the output URL in your browser)")
        logger.info("Press Ctrl+C in the kernel shell to stop the web server and GUI.")

        stdout, stderr = process.communicate()
        if stdout:
             logger.info(f"Flutter web app output:\n{stdout}")
        if stderr:
             logger.warning(f"Flutter web app errors:\n{stderr}")

        return process.returncode

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to launch Flutter web app: {e}")
        logger.error(f"Command: {e.cmd}, Return Code: {e.returncode}")
        return e.returncode
    except Exception as e:
        logger.error(f"An unexpected error occurred while launching Flutter web: {e}")
        return -1

def main():
    """Main function to check prerequisites and launch the GUI."""
    print(" --- UmerOS GUI Launcher --- ")

    # Define the expected path for the Flutter project
    flutter_project_path = os.path.join(os.path.dirname(__file__), "flutter_ui")
    logger.info(f"Looking for Flutter project in: {flutter_project_path}")

    if not os.path.isdir(flutter_project_path):
        logger.critical(f"ERROR: Flutter project directory not found at '{flutter_project_path}'. Please place your Flutter project there.")
        sys.exit(1) # Exit if the project isn't found

    if not check_flutter_installed():
        logger.critical("ERROR: Flutter SDK is not installed or not accessible via PATH/findable by 'where'. Cannot launch GUI.")
        sys.exit(1) # Exit if Flutter isn't available

    # Prompt user for platform
    print("\nSelect platform to launch GUI:")
    print("1. Desktop (Windows/Linux/macOS)")
    print("2. Android")
    print("3. iOS (Requires macOS)")
    print("4. Web (Chrome)")
    choice = input("Enter choice (1-4) or press Enter for Desktop [default: 1]: ").strip()

    if choice == '2':
        exit_code = launch_flutter_android(flutter_project_path)
    elif choice == '3':
        exit_code = launch_flutter_ios(flutter_project_path)
    elif choice == '4':
        exit_code = launch_flutter_web(flutter_project_path)
    else: # Default or '1'
        exit_code = launch_flutter_desktop(flutter_project_path)

    if exit_code != 0:
        logger.error(f"GUI launch failed with exit code {exit_code}. Check logs above.")
        sys.exit(exit_code)
    else:
        logger.info("GUI process finished successfully.")

if __name__ == "__main__":
    main()


    
# #!/usr/bin/env python3
# """
# UmerOS UI Launcher
# Script to launch the Flutter-based graphical user interface (GUI) shell.
# Expects the Flutter project to be located at 'ui/flutter_ui'.
# Requires Flutter SDK to be installed and accessible from PATH.
# """
# import os
# import sys
# import subprocess
# import logging
# import time
# from pathlib import Path # Use pathlib for robust path manipulation

# # Configure logging for this module
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# logger = logging.getLogger(__name__)

# def find_flutter_exe_or_script():
#     """
#     Uses 'where' to find the flutter command (executable or script) and returns its full path.
#     """
#     try:
#         result = subprocess.run(['where', 'flutter'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
#         if result.returncode == 0:
#             flutter_cmd_path_str = result.stdout.strip().split('\n')[0] # Get the first path found
#             flutter_cmd_path = Path(flutter_cmd_path_str)
#             if flutter_cmd_path.exists(): # Check if the file/directory exists
#                 logger.info(f"Flutter command found: {flutter_cmd_path_str}")
#                 # Determine if it's likely a script by checking the extension
#                 if flutter_cmd_path.suffix.lower() in ['.bat', '.cmd', '.ps1']:
#                     logger.info(f"Detected as script ({flutter_cmd_path.suffix}). Will invoke via shell.")
#                 else:
#                     logger.info(f"Detected as executable ({flutter_cmd_path.suffix}).")
#                 return str(flutter_cmd_path) # Return the full path to the script or exe
#             else:
#                 logger.error(f"'where flutter' returned a path that does not exist: {flutter_cmd_path_str}")
#                 return None
#         else:
#             logger.error("'where flutter' returned no results.")
#             return None
#     except FileNotFoundError:
#         logger.error("The 'where' command itself failed. Are you on Windows?")
#         return None
#     except subprocess.TimeoutExpired:
#         logger.error("Finding Flutter path timed out.")
#         return None
#     except Exception as e:
#         logger.error(f"Unexpected error while finding Flutter path: {e}")
#         return None

# def check_flutter_installed():
#     """
#     Check if the 'flutter' command is available using the full path found by 'where'.
#     Handles batch scripts (.bat, .cmd) by invoking them via 'cmd /c'.
#     """
#     flutter_cmd_path = find_flutter_exe_or_script()
#     if not flutter_cmd_path:
#         logger.error("Flutter SDK not found via 'where' command.")
#         logger.error("Please ensure Flutter is installed and 'flutter' command is in your PATH environment variable.")
#         logger.error("Hint: After adding Flutter to PATH, you must open a *NEW* terminal window to see the changes reflected in Python subprocesses.")
#         return False

#     # Determine if the found command is a script that needs shell invocation
#     flutter_path_obj = Path(flutter_cmd_path)
#     is_script = flutter_path_obj.suffix.lower() in ['.bat', '.cmd', '.ps1']

#     try:
#         if is_script:
#             # Use 'cmd /c' to run the batch script
#             cmd_list = ['cmd', '/c', flutter_cmd_path, '--version']
#             logger.info(f"Running Flutter check via shell: {' '.join(cmd_list)}")
#         else:
#             # Run the executable directly
#             cmd_list = [flutter_cmd_path, '--version']
#             logger.info(f"Running Flutter check directly: {' '.join(cmd_list)}")

#         result = subprocess.run(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
#         if result.returncode == 0:
#             logger.info("Flutter SDK found and verified: %s", result.stdout.strip().split('\n')[0])
#             return True
#         else:
#             logger.error(f"Flutter command at '{flutter_cmd_path}' failed with error: %s", result.stderr)
#             return False
#     except FileNotFoundError:
#         logger.error(f"Flutter command not found or not executable at path: {flutter_cmd_path}")
#         return False
#     except subprocess.TimeoutExpired:
#         logger.error("Flutter --version command timed out.")
#         return False
#     except Exception as e:
#         logger.error(f"Unexpected error while checking Flutter: {e}")
#         return False

# def launch_flutter_desktop(flutter_project_path):
#     """Attempt to launch the Flutter app as a desktop application."""
#     logger.info("Attempting to launch Flutter GUI for Desktop...")
#     flutter_cmd_path = find_flutter_exe_or_script()
#     if not flutter_cmd_path:
#         logger.error("Cannot launch GUI: Flutter command path not found.")
#         return -1

#     flutter_path_obj = Path(flutter_cmd_path)
#     is_script = flutter_path_obj.suffix.lower() in ['.bat', '.cmd', '.ps1']

#     try:
#         if is_script:
#             cmd_list = ['cmd', '/c', flutter_cmd_path, 'run', '--release']
#         else:
#             cmd_list = [flutter_cmd_path, 'run', '--release']

#         logger.info(f"Executing command: {' '.join(cmd_list)} in directory: {flutter_project_path}")

#         process = subprocess.Popen(
#             cmd_list,
#             cwd=flutter_project_path,
#             stdout=subprocess.PIPE,
#             stderr=subprocess.STDOUT,
#             text=True,
#             bufsize=1,
#             universal_newlines=True,
#         )

#         logger.info("Flutter desktop app started. Monitoring process... (Press Ctrl+C in the kernel shell to stop the GUI)")

#         stdout, stderr = process.communicate()
#         if stdout:
#              logger.info(f"Flutter desktop app output:\n{stdout}")
#         if stderr:
#              logger.warning(f"Flutter desktop app errors:\n{stderr}")

#         return process.returncode

#     except subprocess.CalledProcessError as e:
#         logger.error(f"Failed to launch Flutter desktop app: {e}")
#         logger.error(f"Command: {e.cmd}, Return Code: {e.returncode}")
#         return e.returncode
#     except Exception as e:
#         logger.error(f"An unexpected error occurred while launching Flutter desktop: {e}")
#         return -1

# def launch_flutter_android(flutter_project_path):
#     """Attempt to launch the Flutter app on an Android device/emulator."""
#     logger.info("Attempting to launch Flutter GUI for Android...")
#     flutter_cmd_path = find_flutter_exe_or_script()
#     if not flutter_cmd_path:
#         logger.error("Cannot launch GUI: Flutter command path not found.")
#         return -1

#     flutter_path_obj = Path(flutter_cmd_path)
#     is_script = flutter_path_obj.suffix.lower() in ['.bat', '.cmd', '.ps1']

#     try:
#         # Check for connected Android devices
#         check_devices_cmd = ['cmd', '/c', flutter_cmd_path, 'devices'] if is_script else [flutter_cmd_path, 'devices']
#         devices_result = subprocess.run(check_devices_cmd, cwd=flutter_project_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
#         if devices_result.returncode != 0 or 'android' not in devices_result.stdout.lower():
#             logger.error("No Android device/emulator found. Please connect a device or start an emulator.")
#             logger.error(f"Flutter devices output:\n{devices_result.stdout}\n{devices_result.stderr}")
#             return -1

#         cmd_list = ['cmd', '/c', flutter_cmd_path, 'run', '-d', 'android', '--release'] if is_script else [flutter_cmd_path, 'run', '-d', 'android', '--release']
#         logger.info(f"Executing command: {' '.join(cmd_list)} in directory: {flutter_project_path}")

#         process = subprocess.Popen(
#             cmd_list,
#             cwd=flutter_project_path,
#             stdout=subprocess.PIPE,
#             stderr=subprocess.STDOUT,
#             text=True,
#             bufsize=1,
#             universal_newlines=True,
#         )

#         logger.info("Flutter Android app started. Monitoring process... (Check your device/emulator)")

#         stdout, stderr = process.communicate()
#         if stdout:
#              logger.info(f"Flutter Android app output:\n{stdout}")
#         if stderr:
#              logger.warning(f"Flutter Android app errors:\n{stderr}")

#         return process.returncode

#     except subprocess.CalledProcessError as e:
#         logger.error(f"Failed to launch Flutter Android app: {e}")
#         logger.error(f"Command: {e.cmd}, Return Code: {e.returncode}")
#         return e.returncode
#     except Exception as e:
#         logger.error(f"An unexpected error occurred while launching Flutter Android: {e}")
#         return -1

# def launch_flutter_ios(flutter_project_path):
#     """Attempt to launch the Flutter app on an iOS simulator/device (requires macOS)."""
#     logger.info("Attempting to launch Flutter GUI for iOS...")
#     flutter_cmd_path = find_flutter_exe_or_script()
#     if not flutter_cmd_path:
#         logger.error("Cannot launch GUI: Flutter command path not found.")
#         return -1

#     flutter_path_obj = Path(flutter_cmd_path)
#     is_script = flutter_path_obj.suffix.lower() in ['.bat', '.cmd', '.ps1']

#     try:
#         # Check for connected iOS devices/simulators
#         check_devices_cmd = ['cmd', '/c', flutter_cmd_path, 'devices'] if is_script else [flutter_cmd_path, 'devices']
#         devices_result = subprocess.run(check_devices_cmd, cwd=flutter_project_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
#         if devices_result.returncode != 0 or 'ios' not in devices_result.stdout.lower():
#             logger.error("No iOS simulator/device found. Ensure Xcode and iOS tools are installed and a simulator is running.")
#             logger.error(f"Flutter devices output:\n{devices_result.stdout}\n{devices_result.stderr}")
#             return -1

#         # Prefer simulator if available
#         device_id = None
#         for line in devices_result.stdout.split('\n'):
#             if 'ios' in line.lower() and 'simulator' in line.lower():
#                 parts = line.split()
#                 if parts:
#                     device_id = parts[0] # Assume first word is ID
#                     break
#         if not device_id:
#              # If no simulator, try first iOS device
#              for line in devices_result.stdout.split('\n'):
#                  if 'ios' in line.lower():
#                      parts = line.split()
#                      if parts:
#                          device_id = parts[0]
#                          break

#         if device_id:
#             cmd_list = ['cmd', '/c', flutter_cmd_path, 'run', '-d', device_id, '--release'] if is_script else [flutter_cmd_path, 'run', '-d', device_id, '--release']
#         else:
#             cmd_list = ['cmd', '/c', flutter_cmd_path, 'run', '-d', 'ios', '--release'] if is_script else [flutter_cmd_path, 'run', '-d', 'ios', '--release']

#         logger.info(f"Executing command: {' '.join(cmd_list)} in directory: {flutter_project_path}")

#         process = subprocess.Popen(
#             cmd_list,
#             cwd=flutter_project_path,
#             stdout=subprocess.PIPE,
#             stderr=subprocess.STDOUT,
#             text=True,
#             bufsize=1,
#             universal_newlines=True,
#         )

#         logger.info("Flutter iOS app started. Monitoring process... (Check your simulator/device)")

#         stdout, stderr = process.communicate()
#         if stdout:
#              logger.info(f"Flutter iOS app output:\n{stdout}")
#         if stderr:
#              logger.warning(f"Flutter iOS app errors:\n{stderr}")

#         return process.returncode

#     except subprocess.CalledProcessError as e:
#         logger.error(f"Failed to launch Flutter iOS app: {e}")
#         logger.error(f"Command: {e.cmd}, Return Code: {e.returncode}")
#         return e.returncode
#     except Exception as e:
#         logger.error(f"An unexpected error occurred while launching Flutter iOS: {e}")
#         return -1

# def launch_flutter_web(flutter_project_path):
#     """Attempt to launch the Flutter app in a web browser."""
#     logger.info("Attempting to launch Flutter GUI for Web...")
#     flutter_cmd_path = find_flutter_exe_or_script()
#     if not flutter_cmd_path:
#         logger.error("Cannot launch GUI: Flutter command path not found.")
#         return -1

#     flutter_path_obj = Path(flutter_cmd_path)
#     is_script = flutter_path_obj.suffix.lower() in ['.bat', '.cmd', '.ps1']

#     try:
#         cmd_list = ['cmd', '/c', flutter_cmd_path, 'run', '-d', 'chrome', '--web-port=7575', '--release'] if is_script else [flutter_cmd_path, 'run', '-d', 'chrome', '--web-port=7575', '--release']

#         logger.info(f"Executing command: {' '.join(cmd_list)} in directory: {flutter_project_path}")

#         process = subprocess.Popen(
#             cmd_list,
#             cwd=flutter_project_path,
#             stdout=subprocess.PIPE,
#             stderr=subprocess.STDOUT,
#             text=True,
#             bufsize=1,
#             universal_newlines=True,
#         )

#         logger.info("Flutter web app started. Monitoring process... (Check http://localhost:7575 or the output URL in your browser)")
#         logger.info("Press Ctrl+C in the kernel shell to stop the web server and GUI.")

#         stdout, stderr = process.communicate()
#         if stdout:
#              logger.info(f"Flutter web app output:\n{stdout}")
#         if stderr:
#              logger.warning(f"Flutter web app errors:\n{stderr}")

#         return process.returncode

#     except subprocess.CalledProcessError as e:
#         logger.error(f"Failed to launch Flutter web app: {e}")
#         logger.error(f"Command: {e.cmd}, Return Code: {e.returncode}")
#         return e.returncode
#     except Exception as e:
#         logger.error(f"An unexpected error occurred while launching Flutter web: {e}")
#         return -1

# def main():
#     """Main function to check prerequisites and launch the GUI."""
#     print(" --- UmerOS GUI Launcher --- ")

#     # Define the expected path for the Flutter project
#     flutter_project_path = os.path.join(os.path.dirname(__file__), "flutter_ui")
#     logger.info(f"Looking for Flutter project in: {flutter_project_path}")

#     if not os.path.isdir(flutter_project_path):
#         logger.critical(f"ERROR: Flutter project directory not found at '{flutter_project_path}'. Please place your Flutter project there.")
#         sys.exit(1) # Exit if the project isn't found

#     if not check_flutter_installed():
#         logger.critical("ERROR: Flutter SDK is not installed or not accessible via PATH/findable by 'where'. Cannot launch GUI.")
#         sys.exit(1) # Exit if Flutter isn't available

#     # Prompt user for platform
#     print("\nSelect platform to launch GUI:")
#     print("1. Desktop (Windows/Linux/macOS)")
#     print("2. Android")
#     print("3. iOS (Requires macOS)")
#     print("4. Web (Chrome)")
#     choice = input("Enter choice (1-4) or press Enter for Desktop [default: 1]: ").strip()

#     if choice == '2':
#         exit_code = launch_flutter_android(flutter_project_path)
#     elif choice == '3':
#         exit_code = launch_flutter_ios(flutter_project_path)
#     elif choice == '4':
#         exit_code = launch_flutter_web(flutter_project_path)
#     else: # Default or '1'
#         exit_code = launch_flutter_desktop(flutter_project_path)

#     if exit_code != 0:
#         logger.error(f"GUI launch failed with exit code {exit_code}. Check logs above.")
#         sys.exit(exit_code)
#     else:
#         logger.info("GUI process finished successfully.")

# if __name__ == "__main__":
#     main()




# # import os
# # import sys
# # import subprocess
# # import logging
# # import time
# # from pathlib import Path # Use pathlib for robust path manipulation

# # # Configure logging for this module
# # logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# # logger = logging.getLogger(__name__)

# # def find_flutter_exe():
# #     """
# #     Uses 'where' to find the flutter.exe executable and returns its full path.
# #     This is the most reliable way to locate it on Windows without relying on PATH resolution.
# #     """
# #     try:
# #         result = subprocess.run(['where', 'flutter'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
# #         if result.returncode == 0:
# #             flutter_exe_path_str = result.stdout.strip().split('\n')[0] # Get the first path found
# #             flutter_exe_path = Path(flutter_exe_path_str)
# #             if flutter_exe_path.is_file():
# #                 logger.info(f"Flutter executable found: {flutter_exe_path_str}")
# #                 return str(flutter_exe_path) # Return the full path to the .exe file
# #             else:
# #                 logger.error(f"'where flutter' returned a path that is not a file: {flutter_exe_path_str}")
# #                 return None
# #         else:
# #             logger.error("'where flutter' returned no results.")
# #             return None
# #     except FileNotFoundError:
# #         logger.error("The 'where' command itself failed. Are you on Windows?")
# #         return None
# #     except subprocess.TimeoutExpired:
# #         logger.error("Finding Flutter path timed out.")
# #         return None
# #     except Exception as e:
# #         logger.error(f"Unexpected error while finding Flutter path: {e}")
# #         return None

# # def check_flutter_installed():
# #     """
# #     Check if the 'flutter' command is available using the full path found by 'where'.
# #     This avoids PATH lookup issues in subprocess calls.
# #     """
# #     flutter_exe_path = find_flutter_exe()
# #     if not flutter_exe_path:
# #         logger.error("Flutter SDK not found via 'where' command.")
# #         logger.error("Please ensure Flutter is installed and 'flutter' command is in your PATH environment variable.")
# #         logger.error("Hint: After adding Flutter to PATH, you must open a *NEW* terminal window to see the changes reflected in Python subprocesses.")
# #         return False

# #     # Run flutter --version using the full executable path
# #     try:
# #         result = subprocess.run([flutter_exe_path, '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
# #         if result.returncode == 0:
# #             logger.info("Flutter SDK found and verified: %s", result.stdout.strip().split('\n')[0])
# #             return True
# #         else:
# #             logger.error(f"Flutter executable at '{flutter_exe_path}' failed with error: %s", result.stderr)
# #             return False
# #     except FileNotFoundError:
# #         logger.error(f"Flutter executable not found at path: {flutter_exe_path}")
# #         return False
# #     except subprocess.TimeoutExpired:
# #         logger.error("Flutter --version command timed out.")
# #         return False
# #     except Exception as e:
# #         logger.error(f"Unexpected error while checking Flutter: {e}")
# #         return False

# # def launch_flutter_desktop(flutter_project_path):
# #     """Attempt to launch the Flutter app as a desktop application."""
# #     logger.info("Attempting to launch Flutter GUI for Desktop...")
# #     flutter_exe_path = find_flutter_exe()
# #     if not flutter_exe_path:
# #         logger.error("Cannot launch GUI: Flutter executable path not found.")
# #         return -1

# #     try:
# #         # Use the full path to the flutter.exe to run the command
# #         cmd = [flutter_exe_path, 'run', '--release']

# #         # Check available devices first (optional, can be removed for speed)
# #         # devices_result = subprocess.run([flutter_exe_path, 'devices'], cwd=flutter_project_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
# #         # if devices_result.returncode == 0:
# #         #     logger.info("Available devices:\n%s", devices_result.stdout)
# #         # else:
# #         #     logger.warning("Could not list devices.")

# #         logger.info(f"Executing command: {' '.join(cmd)} in directory: {flutter_project_path}")

# #         process = subprocess.Popen(
# #             cmd,
# #             cwd=flutter_project_path,
# #             stdout=subprocess.PIPE,
# #             stderr=subprocess.STDOUT,
# #             text=True,
# #             bufsize=1,
# #             universal_newlines=True,
# #         )

# #         logger.info("Flutter desktop app started. Monitoring process... (Press Ctrl+C in the kernel shell to stop the GUI)")

# #         stdout, stderr = process.communicate()
# #         if stdout:
# #              logger.info(f"Flutter desktop app output:\n{stdout}")
# #         if stderr:
# #              logger.warning(f"Flutter desktop app errors:\n{stderr}")

# #         return process.returncode

# #     except subprocess.CalledProcessError as e:
# #         logger.error(f"Failed to launch Flutter desktop app: {e}")
# #         logger.error(f"Command: {e.cmd}, Return Code: {e.returncode}")
# #         return e.returncode
# #     except Exception as e:
# #         logger.error(f"An unexpected error occurred while launching Flutter desktop: {e}")
# #         return -1

# # def launch_flutter_android(flutter_project_path):
# #     """Attempt to launch the Flutter app on an Android device/emulator."""
# #     logger.info("Attempting to launch Flutter GUI for Android...")
# #     flutter_exe_path = find_flutter_exe()
# #     if not flutter_exe_path:
# #         logger.error("Cannot launch GUI: Flutter executable path not found.")
# #         return -1

# #     try:
# #         # Check for connected Android devices
# #         devices_result = subprocess.run([flutter_exe_path, 'devices'], cwd=flutter_project_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
# #         if devices_result.returncode != 0 or 'android' not in devices_result.stdout.lower():
# #             logger.error("No Android device/emulator found. Please connect a device or start an emulator.")
# #             logger.error(f"Flutter devices output:\n{devices_result.stdout}\n{devices_result.stderr}")
# #             return -1

# #         cmd = [flutter_exe_path, 'run', '-d', 'android', '--release']
# #         logger.info(f"Executing command: {' '.join(cmd)} in directory: {flutter_project_path}")

# #         process = subprocess.Popen(
# #             cmd,
# #             cwd=flutter_project_path,
# #             stdout=subprocess.PIPE,
# #             stderr=subprocess.STDOUT,
# #             text=True,
# #             bufsize=1,
# #             universal_newlines=True,
# #         )

# #         logger.info("Flutter Android app started. Monitoring process... (Check your device/emulator)")

# #         stdout, stderr = process.communicate()
# #         if stdout:
# #              logger.info(f"Flutter Android app output:\n{stdout}")
# #         if stderr:
# #              logger.warning(f"Flutter Android app errors:\n{stderr}")

# #         return process.returncode

# #     except subprocess.CalledProcessError as e:
# #         logger.error(f"Failed to launch Flutter Android app: {e}")
# #         logger.error(f"Command: {e.cmd}, Return Code: {e.returncode}")
# #         return e.returncode
# #     except Exception as e:
# #         logger.error(f"An unexpected error occurred while launching Flutter Android: {e}")
# #         return -1

# # def launch_flutter_ios(flutter_project_path):
# #     """Attempt to launch the Flutter app on an iOS simulator/device (requires macOS)."""
# #     logger.info("Attempting to launch Flutter GUI for iOS...")
# #     flutter_exe_path = find_flutter_exe()
# #     if not flutter_exe_path:
# #         logger.error("Cannot launch GUI: Flutter executable path not found.")
# #         return -1

# #     try:
# #         # Check for connected iOS devices/simulators
# #         devices_result = subprocess.run([flutter_exe_path, 'devices'], cwd=flutter_project_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
# #         if devices_result.returncode != 0 or 'ios' not in devices_result.stdout.lower():
# #             logger.error("No iOS simulator/device found. Ensure Xcode and iOS tools are installed and a simulator is running.")
# #             logger.error(f"Flutter devices output:\n{devices_result.stdout}\n{devices_result.stderr}")
# #             return -1

# #         # Prefer simulator if available
# #         device_id = None
# #         for line in devices_result.stdout.split('\n'):
# #             if 'ios' in line.lower() and 'simulator' in line.lower():
# #                 parts = line.split()
# #                 if parts:
# #                     device_id = parts[0] # Assume first word is ID
# #                     break
# #         if not device_id:
# #              # If no simulator, try first iOS device
# #              for line in devices_result.stdout.split('\n'):
# #                  if 'ios' in line.lower():
# #                      parts = line.split()
# #                      if parts:
# #                          device_id = parts[0]
# #                          break

# #         if device_id:
# #             cmd = [flutter_exe_path, 'run', '-d', device_id, '--release'] # Use specific device ID
# #         else:
# #             cmd = [flutter_exe_path, 'run', '-d', 'ios', '--release'] # Fallback

# #         logger.info(f"Executing command: {' '.join(cmd)} in directory: {flutter_project_path}")

# #         process = subprocess.Popen(
# #             cmd,
# #             cwd=flutter_project_path,
# #             stdout=subprocess.PIPE,
# #             stderr=subprocess.STDOUT,
# #             text=True,
# #             bufsize=1,
# #             universal_newlines=True,
# #         )

# #         logger.info("Flutter iOS app started. Monitoring process... (Check your simulator/device)")

# #         stdout, stderr = process.communicate()
# #         if stdout:
# #              logger.info(f"Flutter iOS app output:\n{stdout}")
# #         if stderr:
# #              logger.warning(f"Flutter iOS app errors:\n{stderr}")

# #         return process.returncode

# #     except subprocess.CalledProcessError as e:
# #         logger.error(f"Failed to launch Flutter iOS app: {e}")
# #         logger.error(f"Command: {e.cmd}, Return Code: {e.returncode}")
# #         return e.returncode
# #     except Exception as e:
# #         logger.error(f"An unexpected error occurred while launching Flutter iOS: {e}")
# #         return -1

# # def launch_flutter_web(flutter_project_path):
# #     """Attempt to launch the Flutter app in a web browser."""
# #     logger.info("Attempting to launch Flutter GUI for Web...")
# #     flutter_exe_path = find_flutter_exe()
# #     if not flutter_exe_path:
# #         logger.error("Cannot launch GUI: Flutter executable path not found.")
# #         return -1

# #     try:
# #         cmd = [flutter_exe_path, 'run', '-d', 'chrome', '--web-port=7575', '--release']

# #         logger.info(f"Executing command: {' '.join(cmd)} in directory: {flutter_project_path}")

# #         process = subprocess.Popen(
# #             cmd,
# #             cwd=flutter_project_path,
# #             stdout=subprocess.PIPE,
# #             stderr=subprocess.STDOUT,
# #             text=True,
# #             bufsize=1,
# #             universal_newlines=True,
# #         )

# #         logger.info("Flutter web app started. Monitoring process... (Check http://localhost:7575 or the output URL in your browser)")
# #         logger.info("Press Ctrl+C in the kernel shell to stop the web server and GUI.")

# #         stdout, stderr = process.communicate()
# #         if stdout:
# #              logger.info(f"Flutter web app output:\n{stdout}")
# #         if stderr:
# #              logger.warning(f"Flutter web app errors:\n{stderr}")

# #         return process.returncode

# #     except subprocess.CalledProcessError as e:
# #         logger.error(f"Failed to launch Flutter web app: {e}")
# #         logger.error(f"Command: {e.cmd}, Return Code: {e.returncode}")
# #         return e.returncode
# #     except Exception as e:
# #         logger.error(f"An unexpected error occurred while launching Flutter web: {e}")
# #         return -1

# # def main():
# #     """Main function to check prerequisites and launch the GUI."""
# #     print(" --- UmerOS GUI Launcher --- ")

# #     # Define the expected path for the Flutter project
# #     flutter_project_path = os.path.join(os.path.dirname(__file__), "flutter_ui")
# #     logger.info(f"Looking for Flutter project in: {flutter_project_path}")

# #     if not os.path.isdir(flutter_project_path):
# #         logger.critical(f"ERROR: Flutter project directory not found at '{flutter_project_path}'. Please place your Flutter project there.")
# #         sys.exit(1) # Exit if the project isn't found

# #     if not check_flutter_installed():
# #         logger.critical("ERROR: Flutter SDK is not installed or not accessible via PATH/findable by 'where'. Cannot launch GUI.")
# #         sys.exit(1) # Exit if Flutter isn't available

# #     # Prompt user for platform
# #     print("\nSelect platform to launch GUI:")
# #     print("1. Desktop (Windows/Linux/macOS)")
# #     print("2. Android")
# #     print("3. iOS (Requires macOS)")
# #     print("4. Web (Chrome)")
# #     choice = input("Enter choice (1-4) or press Enter for Desktop [default: 1]: ").strip()

# #     if choice == '2':
# #         exit_code = launch_flutter_android(flutter_project_path)
# #     elif choice == '3':
# #         exit_code = launch_flutter_ios(flutter_project_path)
# #     elif choice == '4':
# #         exit_code = launch_flutter_web(flutter_project_path)
# #     else: # Default or '1'
# #         exit_code = launch_flutter_desktop(flutter_project_path)

# #     if exit_code != 0:
# #         logger.error(f"GUI launch failed with exit code {exit_code}. Check logs above.")
# #         sys.exit(exit_code)
# #     else:
# #         logger.info("GUI process finished successfully.")

# # if __name__ == "__main__":
# #     main()


# # import os
# # import sys
# # import subprocess
# # import logging
# # import time
# # from pathlib import Path # Use pathlib for robust path manipulation

# # # Configure logging for this module
# # logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# # logger = logging.getLogger(__name__)

# # def find_flutter_path():
# #     """Uses 'where' to find the flutter executable and returns its parent directory."""
# #     try:
# #         result = subprocess.run(['where', 'flutter'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
# #         if result.returncode == 0:
# #             flutter_exe_path_str = result.stdout.strip().split('\n')[0] # Get the first path found
# #             flutter_exe_path = Path(flutter_exe_path_str)
# #             if flutter_exe_path.is_file():
# #                 flutter_bin_dir = flutter_exe_path.parent # Get the 'bin' directory
# #                 logger.info(f"Flutter executable found: {flutter_exe_path_str}")
# #                 logger.info(f"Flutter bin directory: {flutter_bin_dir}")
# #                 return str(flutter_bin_dir) # Return as string for PATH manipulation
# #             else:
# #                 logger.error(f"'where flutter' returned a path that is not a file: {flutter_exe_path_str}")
# #                 return None
# #         else:
# #             logger.error("'where flutter' returned no results.")
# #             return None
# #     except FileNotFoundError:
# #         logger.error("The 'where' command itself failed. Are you on Windows?")
# #         return None
# #     except subprocess.TimeoutExpired:
# #         logger.error("Finding Flutter path timed out.")
# #         return None
# #     except Exception as e:
# #         logger.error(f"Unexpected error while finding Flutter path: {e}")
# #         return None

# # def check_flutter_installed():
# #     """Check if the 'flutter' command is available, using the path found by 'where' if necessary."""
# #     flutter_bin_dir = find_flutter_path()
# #     if not flutter_bin_dir:
# #         logger.error("Flutter SDK not found via 'where' command.")
# #         logger.error("Please ensure Flutter is installed and 'flutter' command is in your PATH environment variable.")
# #         logger.error("Hint: After adding Flutter to PATH, you must open a *NEW* terminal window to see the changes reflected in Python subprocesses.")
# #         return False

# #     # Create a copy of the current environment
# #     env = os.environ.copy()
# #     # Prepend the found Flutter bin directory to the PATH for this subprocess
# #     current_path = env.get('PATH', '')
# #     env['PATH'] = f"{flutter_bin_dir};{current_path}"

# #     try:
# #         # Now try running flutter --version using the updated PATH
# #         result = subprocess.run(['flutter', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10, env=env)
# #         if result.returncode == 0:
# #             logger.info("Flutter SDK found and verified: %s", result.stdout.strip().split('\n')[0])
# #             return True
# #         else:
# #             logger.error("Flutter command failed even with updated PATH: %s", result.stderr)
# #             return False
# #     except FileNotFoundError:
# #         logger.error("Flutter command not found in PATH even after prepending Flutter bin dir. PATH might still be incorrect or inaccessible.")
# #         return False
# #     except subprocess.TimeoutExpired:
# #         logger.error("Flutter --version command timed out.")
# #         return False

# # def launch_flutter_desktop(flutter_project_path):
# #     """Attempt to launch the Flutter app as a desktop application."""
# #     logger.info("Attempting to launch Flutter GUI for Desktop...")
# #     flutter_bin_dir = find_flutter_path()
# #     if not flutter_bin_dir:
# #         logger.error("Cannot launch GUI: Flutter path not found.")
# #         return -1

# #     env = os.environ.copy()
# #     current_path = env.get('PATH', '')
# #     env['PATH'] = f"{flutter_bin_dir};{current_path}"

# #     try:
# #         # Attempt to run for the host platform (Windows in this case)
# #         # First, check available devices
# #         devices_result = subprocess.run(['flutter', 'devices'], cwd=flutter_project_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
# #         if devices_result.returncode == 0:
# #             logger.info("Available devices:\n%s", devices_result.stdout)
# #             # Look for Windows device
# #             if 'windows' in devices_result.stdout.lower():
# #                 cmd = ['flutter', 'run', '-d', 'windows', '--release']
# #             elif 'linux' in devices_result.stdout.lower():
# #                  cmd = ['flutter', 'run', '-d', 'linux', '--release']
# #             elif 'macos' in devices_result.stdout.lower():
# #                  cmd = ['flutter', 'run', '-d', 'macos', '--release']
# #             else:
# #                 # Default to host platform if specific one isn't listed
# #                 logger.info("Defaulting to host platform launch (likely Windows).")
# #                 cmd = ['flutter', 'run', '--release']
# #         else:
# #             logger.warning("Could not list devices. Defaulting to host platform launch.")
# #             cmd = ['flutter', 'run', '--release']

# #         logger.info(f"Executing command: {' '.join(cmd)} in directory: {flutter_project_path}")

# #         process = subprocess.Popen(
# #             cmd,
# #             cwd=flutter_project_path,
# #             stdout=subprocess.PIPE,
# #             stderr=subprocess.STDOUT,
# #             text=True,
# #             bufsize=1,
# #             universal_newlines=True,
# #             env=env
# #         )

# #         logger.info("Flutter desktop app started. Monitoring process... (Press Ctrl+C in the kernel shell to stop the GUI)")

# #         stdout, stderr = process.communicate()
# #         if stdout:
# #              logger.info(f"Flutter desktop app output:\n{stdout}")
# #         if stderr:
# #              logger.warning(f"Flutter desktop app errors:\n{stderr}")

# #         return process.returncode

# #     except subprocess.CalledProcessError as e:
# #         logger.error(f"Failed to launch Flutter desktop app: {e}")
# #         logger.error(f"Command: {e.cmd}, Return Code: {e.returncode}")
# #         return e.returncode
# #     except Exception as e:
# #         logger.error(f"An unexpected error occurred while launching Flutter desktop: {e}")
# #         return -1

# # def launch_flutter_android(flutter_project_path):
# #     """Attempt to launch the Flutter app on an Android device/emulator."""
# #     logger.info("Attempting to launch Flutter GUI for Android...")
# #     flutter_bin_dir = find_flutter_path()
# #     if not flutter_bin_dir:
# #         logger.error("Cannot launch GUI: Flutter path not found.")
# #         return -1

# #     env = os.environ.copy()
# #     current_path = env.get('PATH', '')
# #     env['PATH'] = f"{flutter_bin_dir};{current_path}"

# #     try:
# #         # Check for connected Android devices
# #         devices_result = subprocess.run(['flutter', 'devices'], cwd=flutter_project_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
# #         if devices_result.returncode != 0 or 'android' not in devices_result.stdout.lower():
# #             logger.error("No Android device/emulator found. Please connect a device or start an emulator.")
# #             logger.error(f"Flutter devices output:\n{devices_result.stdout}\n{devices_result.stderr}")
# #             return -1

# #         cmd = ['flutter', 'run', '-d', 'android', '--release']
# #         logger.info(f"Executing command: {' '.join(cmd)} in directory: {flutter_project_path}")

# #         process = subprocess.Popen(
# #             cmd,
# #             cwd=flutter_project_path,
# #             stdout=subprocess.PIPE,
# #             stderr=subprocess.STDOUT,
# #             text=True,
# #             bufsize=1,
# #             universal_newlines=True,
# #             env=env
# #         )

# #         logger.info("Flutter Android app started. Monitoring process... (Check your device/emulator)")

# #         stdout, stderr = process.communicate()
# #         if stdout:
# #              logger.info(f"Flutter Android app output:\n{stdout}")
# #         if stderr:
# #              logger.warning(f"Flutter Android app errors:\n{stderr}")

# #         return process.returncode

# #     except subprocess.CalledProcessError as e:
# #         logger.error(f"Failed to launch Flutter Android app: {e}")
# #         logger.error(f"Command: {e.cmd}, Return Code: {e.returncode}")
# #         return e.returncode
# #     except Exception as e:
# #         logger.error(f"An unexpected error occurred while launching Flutter Android: {e}")
# #         return -1

# # def launch_flutter_ios(flutter_project_path):
# #     """Attempt to launch the Flutter app on an iOS simulator/device (requires macOS)."""
# #     logger.info("Attempting to launch Flutter GUI for iOS...")
# #     flutter_bin_dir = find_flutter_path()
# #     if not flutter_bin_dir:
# #         logger.error("Cannot launch GUI: Flutter path not found.")
# #         return -1

# #     env = os.environ.copy()
# #     current_path = env.get('PATH', '')
# #     env['PATH'] = f"{flutter_bin_dir};{current_path}"

# #     try:
# #         # Check for connected iOS devices/simulators
# #         devices_result = subprocess.run(['flutter', 'devices'], cwd=flutter_project_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
# #         if devices_result.returncode != 0 or 'ios' not in devices_result.stdout.lower():
# #             logger.error("No iOS simulator/device found. Ensure Xcode and iOS tools are installed and a simulator is running.")
# #             logger.error(f"Flutter devices output:\n{devices_result.stdout}\n{devices_result.stderr}")
# #             return -1

# #         # Prefer simulator if available
# #         device_id = None
# #         for line in devices_result.stdout.split('\n'):
# #             if 'ios' in line.lower() and 'simulator' in line.lower():
# #                 parts = line.split()
# #                 if parts:
# #                     device_id = parts[0] # Assume first word is ID
# #                     break
# #         if not device_id:
# #              # If no simulator, try first iOS device
# #              for line in devices_result.stdout.split('\n'):
# #                  if 'ios' in line.lower():
# #                      parts = line.split()
# #                      if parts:
# #                          device_id = parts[0]
# #                          break

# #         if device_id:
# #             cmd = ['flutter', 'run', '-d', device_id, '--release'] # Use specific device ID
# #         else:
# #             cmd = ['flutter', 'run', '-d', 'ios', '--release'] # Fallback

# #         logger.info(f"Executing command: {' '.join(cmd)} in directory: {flutter_project_path}")

# #         process = subprocess.Popen(
# #             cmd,
# #             cwd=flutter_project_path,
# #             stdout=subprocess.PIPE,
# #             stderr=subprocess.STDOUT,
# #             text=True,
# #             bufsize=1,
# #             universal_newlines=True,
# #             env=env
# #         )

# #         logger.info("Flutter iOS app started. Monitoring process... (Check your simulator/device)")

# #         stdout, stderr = process.communicate()
# #         if stdout:
# #              logger.info(f"Flutter iOS app output:\n{stdout}")
# #         if stderr:
# #              logger.warning(f"Flutter iOS app errors:\n{stderr}")

# #         return process.returncode

# #     except subprocess.CalledProcessError as e:
# #         logger.error(f"Failed to launch Flutter iOS app: {e}")
# #         logger.error(f"Command: {e.cmd}, Return Code: {e.returncode}")
# #         return e.returncode
# #     except Exception as e:
# #         logger.error(f"An unexpected error occurred while launching Flutter iOS: {e}")
# #         return -1

# # def launch_flutter_web(flutter_project_path):
# #     """Attempt to launch the Flutter app in a web browser."""
# #     logger.info("Attempting to launch Flutter GUI for Web...")
# #     flutter_bin_dir = find_flutter_path()
# #     if not flutter_bin_dir:
# #         logger.error("Cannot launch GUI: Flutter path not found.")
# #         return -1

# #     env = os.environ.copy()
# #     current_path = env.get('PATH', '')
# #     env['PATH'] = f"{flutter_bin_dir};{current_path}"

# #     try:
# #         cmd = ['flutter', 'run', '-d', 'chrome', '--web-port=7575', '--release']

# #         logger.info(f"Executing command: {' '.join(cmd)} in directory: {flutter_project_path}")

# #         process = subprocess.Popen(
# #             cmd,
# #             cwd=flutter_project_path,
# #             stdout=subprocess.PIPE,
# #             stderr=subprocess.STDOUT,
# #             text=True,
# #             bufsize=1,
# #             universal_newlines=True,
# #             env=env
# #         )

# #         logger.info("Flutter web app started. Monitoring process... (Check http://localhost:7575 or the output URL in your browser)")
# #         logger.info("Press Ctrl+C in the kernel shell to stop the web server and GUI.")

# #         stdout, stderr = process.communicate()
# #         if stdout:
# #              logger.info(f"Flutter web app output:\n{stdout}")
# #         if stderr:
# #              logger.warning(f"Flutter web app errors:\n{stderr}")

# #         return process.returncode

# #     except subprocess.CalledProcessError as e:
# #         logger.error(f"Failed to launch Flutter web app: {e}")
# #         logger.error(f"Command: {e.cmd}, Return Code: {e.returncode}")
# #         return e.returncode
# #     except Exception as e:
# #         logger.error(f"An unexpected error occurred while launching Flutter web: {e}")
# #         return -1

# # def main():
# #     """Main function to check prerequisites and launch the GUI."""
# #     print(" --- UmerOS GUI Launcher --- ")

# #     # Define the expected path for the Flutter project
# #     flutter_project_path = os.path.join(os.path.dirname(__file__), "flutter_ui")
# #     logger.info(f"Looking for Flutter project in: {flutter_project_path}")

# #     if not os.path.isdir(flutter_project_path):
# #         logger.critical(f"ERROR: Flutter project directory not found at '{flutter_project_path}'. Please place your Flutter project there.")
# #         sys.exit(1) # Exit if the project isn't found

# #     if not check_flutter_installed():
# #         logger.critical("ERROR: Flutter SDK is not installed or not accessible via PATH/findable by 'where'. Cannot launch GUI.")
# #         sys.exit(1) # Exit if Flutter isn't available

# #     # Prompt user for platform
# #     print("\nSelect platform to launch GUI:")
# #     print("1. Desktop (Windows/Linux/macOS)")
# #     print("2. Android")
# #     print("3. iOS (Requires macOS)")
# #     print("4. Web (Chrome)")
# #     choice = input("Enter choice (1-4) or press Enter for Desktop [default: 1]: ").strip()

# #     if choice == '2':
# #         exit_code = launch_flutter_android(flutter_project_path)
# #     elif choice == '3':
# #         exit_code = launch_flutter_ios(flutter_project_path)
# #     elif choice == '4':
# #         exit_code = launch_flutter_web(flutter_project_path)
# #     else: # Default or '1'
# #         exit_code = launch_flutter_desktop(flutter_project_path)

# #     if exit_code != 0:
# #         logger.error(f"GUI launch failed with exit code {exit_code}. Check logs above.")
# #         sys.exit(exit_code)
# #     else:
# #         logger.info("GUI process finished successfully.")

# # if __name__ == "__main__":
# #     main()













# # # import os
# # # import sys
# # # import subprocess
# # # import logging
# # # import time

# # # # Configure logging for this module
# # # logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# # # logger = logging.getLogger(__name__)

# # # def check_flutter_installed():
# # #     """Check if the 'flutter' command is available in the system PATH."""
# # #     import subprocess
# # #     import os
# # #     # Refresh environment for subprocess
# # #     env = os.environ.copy()

# # #     try:
# # #         # Try running 'where' first to locate the flutter executable
# # #         where_result = subprocess.run(['where', 'flutter'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10, env=env)
# # #         if where_result.returncode == 0:
# # #             flutter_exe_path = where_result.stdout.strip().split('\n')[0] # Get the first path found
# # #             logger.info(f"Flutter executable found via 'where' command: {flutter_exe_path}")
            
# # #             # Use the path found by 'where' to execute the command directly
# # #             # This bypasses potential PATH lookup issues in subprocess
# # #             result = subprocess.run([flutter_exe_path, '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10, env=env)
# # #             if result.returncode == 0:
# # #                 logger.info("Flutter SDK found and verified: %s", result.stdout.strip().split('\n')[0])
# # #                 return True
# # #             else:
# # #                 logger.error("Flutter command at '{flutter_exe_path}' failed: %s", result.stderr)
# # #                 return False
# # #         else:
# # #             logger.error("'where flutter' returned no results. Flutter likely not in PATH.")
# # #             return False

# # #     except FileNotFoundError:
# # #         logger.error("The 'where' command itself failed. Are you on Windows?")
# # #         # Fallback to original method if 'where' is not available (non-Windows)
# # #         try:
# # #             result = subprocess.run(['flutter', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10, env=env)
# # #             if result.returncode == 0:
# # #                 logger.info("Flutter SDK found: %s", result.stdout.strip().split('\n')[0])
# # #                 return True
# # #             else:
# # #                 logger.error("Flutter command failed: %s", result.stderr)
# # #                 return False
# # #         except FileNotFoundError:
# # #             logger.error("Flutter SDK not found in PATH via fallback method. Please ensure Flutter is installed and 'flutter' command is in your PATH environment variable.")
# # #             logger.error("Hint: After adding Flutter to PATH, you must open a *NEW* terminal window to see the changes reflected in Python subprocesses.")
# # #             return False
# # #     except subprocess.TimeoutExpired:
# # #         logger.error("Flutter command timed out. SDK might be corrupted or slow.")
# # #         return False
# # #     except Exception as e:
# # #         logger.error(f"Unexpected error while checking Flutter: {e}")
# # #         return False


# # # def launch_flutter_desktop(flutter_project_path):
# # #     """Attempt to launch the Flutter app as a desktop application."""
# # #     logger.info("Attempting to launch Flutter GUI for Desktop...")
# # #     # Refresh environment for subprocess
# # #     env = os.environ.copy()
# # #     try:
# # #         # Find the flutter executable path first
# # #         where_result = subprocess.run(['where', 'flutter'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10, env=env)
# # #         if where_result.returncode == 0:
# # #             flutter_exe_path = where_result.stdout.strip().split('\n')[0]
# # #             logger.info(f"Using Flutter executable found at: {flutter_exe_path}")
# # #             cmd = [flutter_exe_path, 'run', '--release']
# # #         else:
# # #             logger.warning("'where flutter' failed, falling back to generic 'flutter' command. Ensure PATH is correct.")
# # #             cmd = ['flutter', 'run', '--release']

# # #         logger.info(f"Executing command: {' '.join(cmd)} in directory: {flutter_project_path}")

# # #         # Run the flutter command in the project directory, passing the environment
# # #         process = subprocess.Popen(
# # #             cmd,
# # #             cwd=flutter_project_path,
# # #             stdout=subprocess.PIPE,
# # #             stderr=subprocess.STDOUT, # Redirect stderr to stdout for unified logging
# # #             text=True,
# # #             bufsize=1,
# # #             universal_newlines=True,
# # #             env=env
# # #         )

# # #         logger.info("Flutter app started. Monitoring process... (Press Ctrl+C in the kernel shell to stop the GUI)")

# # #         stdout, stderr = process.communicate()
# # #         if stdout:
# # #              logger.info(f"Flutter app output:\n{stdout}")
# # #         if stderr:
# # #              logger.warning(f"Flutter app errors:\n{stderr}")

# # #         return process.returncode

# # #     except subprocess.CalledProcessError as e:
# # #         logger.error(f"Failed to launch Flutter app: {e}")
# # #         logger.error(f"Command: {e.cmd}, Return Code: {e.returncode}")
# # #         return e.returncode
# # #     except Exception as e:
# # #         logger.error(f"An unexpected error occurred while launching Flutter: {e}")
# # #         return -1


# # # def launch_flutter_web(flutter_project_path):
# # #     """Attempt to launch the Flutter app in a web browser."""
# # #     logger.info("Attempting to launch Flutter GUI for Web...")
# # #     # Refresh environment for subprocess
# # #     env = os.environ.copy()
# # #     try:
# # #         # Find the flutter executable path first
# # #         where_result = subprocess.run(['where', 'flutter'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10, env=env)
# # #         if where_result.returncode == 0:
# # #             flutter_exe_path = where_result.stdout.strip().split('\n')[0]
# # #             logger.info(f"Using Flutter executable found at: {flutter_exe_path}")
# # #             cmd = [flutter_exe_path, 'run', '-d', 'chrome', '--web-port=7575', '--release']
# # #         else:
# # #             logger.warning("'where flutter' failed, falling back to generic 'flutter' command. Ensure PATH is correct.")
# # #             cmd = ['flutter', 'run', '-d', 'chrome', '--web-port=7575', '--release']

# # #         logger.info(f"Executing command: {' '.join(cmd)} in directory: {flutter_project_path}")

# # #         process = subprocess.Popen(
# # #             cmd,
# # #             cwd=flutter_project_path,
# # #             stdout=subprocess.PIPE,
# # #             stderr=subprocess.STDOUT,
# # #             text=True,
# # #             bufsize=1,
# # #             universal_newlines=True,
# # #             env=env
# # #         )

# # #         logger.info("Flutter web app started. Monitoring process... (Check http://localhost:7575 or the output URL in your browser)")
# # #         logger.info("Press Ctrl+C in the kernel shell to stop the web server and GUI.")

# # #         stdout, stderr = process.communicate()
# # #         if stdout:
# # #              logger.info(f"Flutter web app output:\n{stdout}")
# # #         if stderr:
# # #              logger.warning(f"Flutter web app errors:\n{stderr}")

# # #         return process.returncode

# # #     except subprocess.CalledProcessError as e:
# # #         logger.error(f"Failed to launch Flutter web app: {e}")
# # #         logger.error(f"Command: {e.cmd}, Return Code: {e.returncode}")
# # #         return e.returncode
# # #     except Exception as e:
# # #         logger.error(f"An unexpected error occurred while launching Flutter web: {e}")
# # #         return -1


# # # def main():
# # #     """Main function to check prerequisites and launch the GUI."""
# # #     print(" --- UmerOS GUI Launcher --- ")
    
# # #     # Define the expected path for the Flutter project
# # #     flutter_project_path = os.path.join(os.path.dirname(__file__), "flutter_ui")
# # #     logger.info(f"Looking for Flutter project in: {flutter_project_path}")

# # #     if not os.path.isdir(flutter_project_path):
# # #         logger.critical(f"ERROR: Flutter project directory not found at '{flutter_project_path}'. Please place your Flutter project there.")
# # #         sys.exit(1) # Exit if the project isn't found

# # #     if not check_flutter_installed():
# # #         logger.critical("ERROR: Flutter SDK is not installed or not in PATH. Cannot launch GUI.")
# # #         sys.exit(1) # Exit if Flutter isn't available

# # #     # Attempt to launch for Desktop first
# # #     logger.info("Trying to launch as Desktop Application...")
# # #     exit_code = launch_flutter_desktop(flutter_project_path)
    
# # #     if exit_code != 0:
# # #         logger.warning(f"Desktop launch failed (exit code {exit_code}). Trying Web launch...")
# # #         # If desktop fails, try web
# # #         exit_code = launch_flutter_web(flutter_project_path)
    
# # #     if exit_code != 0:
# # #         logger.error(f"GUI launch failed with exit code {exit_code}. Check logs above.")
# # #         sys.exit(exit_code)
# # #     else:
# # #         logger.info("GUI process finished successfully.")

# # # if __name__ == "__main__":
# # #     main()