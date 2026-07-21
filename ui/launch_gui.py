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

# Configure logging for this module
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_flutter_installed():
    """Check if the 'flutter' command is available in the system PATH."""
    try:
        result = subprocess.run(['flutter', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
        if result.returncode == 0:
            logger.info("Flutter SDK found: %s", result.stdout.strip().split('\n')[0])
            return True
        else:
            logger.error("Flutter command failed: %s", result.stderr)
            return False
    except FileNotFoundError:
        logger.error("Flutter SDK not found in PATH. Please install Flutter and ensure it's added to your PATH environment variable.")
        return False
    except subprocess.TimeoutExpired:
        logger.error("Flutter command timed out. SDK might be corrupted or slow.")
        return False

def launch_flutter_desktop(flutter_project_path):
    """Attempt to launch the Flutter app as a desktop application."""
    logger.info("Attempting to launch Flutter GUI for Desktop...")
    try:
        # Common desktop targets: windows, linux, macos
        # We'll try 'windows' first if on Windows, 'linux' if on Linux, etc.
        # Using 'flutter run' with no specific device ID often defaults to the host platform.
        # For more control, you might specify --device-id=windows, --device-id=linux, etc.
        # cmd = ['flutter', 'run', '-d', 'windows', '--release'] # Example for Windows
        cmd = ['flutter', 'run', '--release'] # Generic command, defaults to host platform if available
        
        logger.info(f"Executing command: {' '.join(cmd)} in directory: {flutter_project_path}")
        
        # Run the flutter command in the project directory
        process = subprocess.Popen(
            cmd,
            cwd=flutter_project_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, # Redirect stderr to stdout for unified logging
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        logger.info("Flutter app started. Monitoring process... (Press Ctrl+C in the kernel shell to stop the GUI)")

        # Optionally, read output from the Flutter app
        # This is useful for debugging but can be omitted if it causes issues.
        # while True:
        #     output = process.stdout.readline()
        #     if output == '' and process.poll() is not None:
        #         break
        #     if output:
        #         print(f"[Flutter Output]: {output.strip()}")
        # rc = process.poll()
        # return rc

        # Wait for the process to finish (this happens when the GUI window is closed or the process is terminated)
        # Using communicate() is safer than wait() for capturing output if needed later.
        stdout, stderr = process.communicate()
        if stdout:
             logger.info(f"Flutter app output:\n{stdout}")
        if stderr:
             logger.warning(f"Flutter app errors:\n{stderr}")

        return process.returncode

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to launch Flutter app: {e}")
        logger.error(f"Command: {e.cmd}, Return Code: {e.returncode}")
        return e.returncode
    except Exception as e:
        logger.error(f"An unexpected error occurred while launching Flutter: {e}")
        return -1

def launch_flutter_web(flutter_project_path):
    """Attempt to launch the Flutter app in a web browser."""
    logger.info("Attempting to launch Flutter GUI for Web...")
    try:
        # Find an available port (optional, Flutter usually handles this)
        # port = 7575 # Example port
        cmd = ['flutter', 'run', '-d', 'chrome', '--web-port=7575', '--release']
        # Alternative: flutter run -d web-server --web-port=7575 --release (runs headless server)
        
        logger.info(f"Executing command: {' '.join(cmd)} in directory: {flutter_project_path}")
        
        process = subprocess.Popen(
            cmd,
            cwd=flutter_project_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        logger.info("Flutter web app started. Monitoring process... (Check http://localhost:7575 or the output URL in your browser)")
        logger.info("Press Ctrl+C in the kernel shell to stop the web server and GUI.")

        # Wait for the process to finish
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
        logger.critical("ERROR: Flutter SDK is not installed or not in PATH. Cannot launch GUI.")
        sys.exit(1) # Exit if Flutter isn't available

    # Attempt to launch for Desktop first
    logger.info("Trying to launch as Desktop Application...")
    exit_code = launch_flutter_desktop(flutter_project_path)
    
    if exit_code != 0:
        logger.warning(f"Desktop launch failed (exit code {exit_code}). Trying Web launch...")
        # If desktop fails, try web
        exit_code = launch_flutter_web(flutter_project_path)
    
    if exit_code != 0:
        logger.error(f"GUI launch failed with exit code {exit_code}. Check logs above.")
        sys.exit(exit_code)
    else:
        logger.info("GUI process finished successfully.")

if __name__ == "__main__":
    main()