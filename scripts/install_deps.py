import subprocess
import sys

def main():
    """Install required packages from requirements.txt using the current Python interpreter."""
    result = subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print("Error installing dependencies:", result.stderr, file=sys.stderr)
        sys.exit(result.returncode)

if __name__ == "__main__":
    main()
