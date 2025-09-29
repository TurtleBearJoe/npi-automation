# NPI Automation Tool

This tool enriches provider data with National Provider Identifier (NPI) information using a simple web interface. It is powered by Streamlit and queries the public CMS NPPES NPI Registry API.

**Data Source:** [CMS National Plan and Provider Enumeration System (NPPES) NPI Registry](https://npiregistry.cms.hhs.gov/)

## Requirements

- **Python 3.8+**
- Python packages: `pandas`, `requests`, `streamlit`

## How to Run the Application

1.  **Install Dependencies**:
    First, make sure you have all the necessary packages installed. Open your terminal or command prompt and run the following command from the project's root directory:

    ```bash
    pip install -r requirements.txt
    ```

2.  **Launch the Application**:
    Once the dependencies are installed, you can start the Streamlit application with this command:

    ```bash
    streamlit run app.py
    ```

    Your web browser should automatically open a new tab with the application running.

## Using the Tool

1.  **Upload Your Data**:
    Click the "Upload your CSV file" button and select the CSV file containing your provider data. The application will show you a preview of the first few rows.

2.  **Map Your Columns**:
    From the dropdown menus, select the columns in your file that correspond to the search fields. You can map fields for:
    -   Provider Last Name
    -   Provider First Name
    -   Institution Name
    -   City
    -   State

    *Note: You must map at least one field to proceed. For best results, provide as much information as possible.*

3.  **Process and Download**:
    -   Click the "Process File" button to begin the NPI lookup. A progress bar will show the status of the search.
    -   Once processing is complete, the results will be displayed on the screen.
    -   Click the "Download Results as CSV" button to save the enriched data to your computer.

## How It Works

The application processes your CSV file row by row, sending queries to the NPI Registry API based on the information you've provided. It uses a series of search strategies to find the most accurate matches and returns a new CSV file that includes the original data from your file, plus the NPI number and other details retrieved from the registry.

---

## Standalone Desktop Application

For convenience, you can build a standalone executable version of the application. This allows you to run the tool as a desktop app without using the command line.

### How to Build and Run the Executable

1.  **Build the Application**:
    First, ensure you have installed all the dependencies, including `pyinstaller`, by running:
    ```bash
    pip install -r requirements.txt
    ```
    Then, run the following command from the project's root directory to build the executable:
    ```bash
    pyinstaller --name "npi_automation_tool" --onefile --windowed --add-data "app.py:." --add-data "npi_utils.py:." run_app.py
    ```

2.  **Find the Executable**:
    After the build process is complete, navigate to the `dist/` folder that has been created in your project directory.

3.  **Run the Application**:
    Inside the `dist/` folder, you will find a file named `npi_automation_tool` (or `npi_automation_tool.exe` on Windows). Double-click this file to launch the application. It may take a few moments to start up.

The same user interface will open in a new window, ready for you to use.
