import subprocess
import os
import sys
import time
import webbrowser
import socket

def get_path(filename):
    """ Get the absolute path to a file, accommodating PyInstaller's temporary folder. """
    if hasattr(sys, "_MEIPASS"):
        # Running in a PyInstaller bundle
        return os.path.join(sys._MEIPASS, filename)
    # Running in a normal Python environment
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

def find_free_port():
    """Find a free port to run Streamlit on."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port

def main():
    """
    This is the entry point for the executable.
    It runs the Streamlit app and automatically opens the browser.
    """
    app_path = get_path('app.py')
    port = find_free_port()

    # Get the Python executable bundled with PyInstaller
    if hasattr(sys, "_MEIPASS"):
        # Running in PyInstaller bundle - use bundled Python
        python_exe = sys.executable
        streamlit_script = os.path.join(sys._MEIPASS, 'streamlit_run.py')
    else:
        # Running in normal Python environment
        python_exe = sys.executable
        streamlit_script = None

    # Command to run the streamlit app
    if streamlit_script and os.path.exists(streamlit_script):
        command = [python_exe, streamlit_script, app_path, "--server.port", str(port), "--server.headless", "true"]
    else:
        command = [python_exe, "-m", "streamlit", "run", app_path, "--server.port", str(port), "--server.headless", "true"]

    try:
        print(f"Starting NPI Automation Tool on port {port}...")
        print("Please wait while the application loads...")

        # Start Streamlit in the background
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )

        # Wait a few seconds for Streamlit to start
        time.sleep(5)

        # Open the browser
        url = f"http://localhost:{port}"
        print(f"Opening browser at {url}")
        webbrowser.open(url)

        print("\nNPI Automation Tool is running!")
        print("Close this window to stop the application.")

        # Wait for the process to complete
        process.wait()

    except FileNotFoundError:
        print("Error: Could not start the application.")
        print("Please ensure all required files are present.")
        input("Press Enter to exit...")
    except Exception as e:
        print(f"An error occurred: {e}")
        input("Press Enter to exit...")

if __name__ == "__main__":
    main()