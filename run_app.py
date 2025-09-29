import subprocess
import os
import sys

def get_path(filename):
    """ Get the absolute path to a file, accommodating PyInstaller's temporary folder. """
    if hasattr(sys, "_MEIPASS"):
        # Running in a PyInstaller bundle
        return os.path.join(sys._MEIPASS, filename)
    # Running in a normal Python environment
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

def main():
    """
    This is the entry point for the executable.
    It runs the Streamlit app using subprocess.
    """
    app_path = get_path('app.py')

    # Command to run the streamlit app
    command = ["streamlit", "run", app_path]

    try:
        # Execute the command
        process = subprocess.Popen(command)
        process.wait()  # Wait for the process to complete
    except FileNotFoundError:
        print("Error: 'streamlit' command not found.")
        print("Please ensure Streamlit is installed and in your system's PATH.")
    except Exception as e:
        print(f"An error occurred while trying to run the Streamlit app: {e}")

if __name__ == "__main__":
    main()