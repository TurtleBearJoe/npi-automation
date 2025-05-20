# NPI Automation

This project enriches provider data with National Provider Identifier (NPI) information using the public NPI Registry API.

## Requirements

- **Python 3.8+**
- Python packages: `pandas`, `requests`

Install dependencies with:

```bash
pip install pandas requests
```

## Preparing Data

1. Place your CSV files inside the `input/` directory (create it if it does not exist).
2. Each row should contain provider details. Column names can vary; `config.json` maps common alternatives to the names the script expects.
3. At minimum, the following columns are required:
   - For **individuals**: `last_name`
   - For **institutions**: `institution_name`

Columns such as `first_name`, `city` and `state` improve search accuracy and may appear under many different headings (e.g. `First Name`, `organization`, `facility_name`). See `config.json` for the full list of recognised names.

## Running the Script

From the repository directory run:

```bash
python npi-automation.py
```

The script will:

1. Create `input/` and `output/` folders if they do not exist.
2. List available CSV files in `input/` and prompt you to choose one.
3. Map your column names according to `config.json` and detect whether the data contains individual or institutional providers.
4. Query the NPI Registry using several search strategies until matches are found.
5. Write a results CSV to the `output/` folder. The filename will include a timestamp (e.g. `mydata_npi_20240101_120000.csv`).
6. Log any errors to `<output_file>_errors.log` and track progress in `<output_file>_progress.json` so the script can resume if interrupted.

## Output

The output CSV includes the original input fields, the NPI number, basic provider information and address details for the first matched location. Endpoint specific fields are included when available.

## Tips

- Ensure your input CSV uses UTF‑8 encoding.
- If no matches are found, check the error log for details.
- The script requires internet access to contact the NPI Registry API.

