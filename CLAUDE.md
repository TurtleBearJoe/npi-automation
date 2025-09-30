# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Streamlit web application that enriches healthcare provider data with National Provider Identifier (NPI) numbers by querying the CMS NPPES NPI Registry API. The tool processes CSV files containing provider information and returns enriched data with NPI numbers and additional provider details.

**Live Deployment**: The app is deployed on Streamlit Cloud and updates automatically from the GitHub repository.

## Development Commands

### Running the Application

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
streamlit run app.py
```

### Building Standalone Executable

```bash
# Build Windows executable (if build_exe.bat exists)
build_exe.bat

# Manual build
pyinstaller --name "npi_automation_tool" --onefile --windowed --add-data "app.py:." --add-data "npi_utils.py:." run_app.py
```

The executable will be in `dist/` folder.

## Architecture

### Core Components

1. **app.py** - Streamlit UI layer
   - Handles file upload and column mapping
   - Provides state and taxonomy filtering UI
   - Displays results and download button
   - Uses Streamlit session state for filter persistence

2. **npi_utils.py** - Business logic layer
   - `NPILookup` class: Handles API communication with CMS NPI Registry
   - `TextCleaner` class: Normalizes and formats text data
   - `process_dataframe()`: Main orchestration function
   - Implements 6 search strategies (most specific to least specific)
   - Handles API pagination (200 results per page)

3. **config.py** - Configuration layer
   - Column name mapping variations for auto-detection
   - `auto_detect_columns()`: Fuzzy matching for CSV columns
   - `validate_required_fields()`: Ensures required data is present

### Data Flow

```
CSV Upload → Column Auto-detection → User Mapping Confirmation →
Row-by-row Processing → Search Strategy Application →
Taxonomy & State Filtering → Results (with all addresses) → CSV Download
```

### Search Strategy Hierarchy

The application tries 6 strategies in order, stopping at the first successful match:

1. First name + Last name + City + State (most specific)
2. First name + Last name + State
3. Last name + City + State
4. Last name + State
5. First name + Last name
6. Last name only (broadest)

Each strategy includes verification logic to ensure returned results match the input criteria.

### API Pagination

The CMS NPI Registry API returns a maximum of 200 results per request. The `search_npi()` method automatically handles pagination using the `skip` parameter to retrieve all matching results.

### Text Formatting

All text output uses **Proper Case (Title Case)** instead of UPPERCASE:
- Names: "John Smith" not "JOHN SMITH"
- Addresses: "123 Main St" not "123 MAIN ST"
- Cities: "Charlotte" not "CHARLOTTE"
- State abbreviations remain uppercase: "NC", "GA"

This is handled by `TextCleaner.to_proper_case()` applied during result building.

### Filtering System

**State Filter**:
- Users select state names (e.g., "Georgia", "North Carolina")
- Internally converted to abbreviations for API (e.g., "GA", "NC")
- Filters results by checking all addresses (main, practice locations, endpoints)

**Taxonomy Filter**:
- Keyword-based partial matching (case-insensitive)
- Example: "surgery" matches "Neurological Surgery", "Orthopedic Surgery"
- Filters applied after search, before results display

## Important Implementation Details

### Streamlit Cloud Deployment

**CRITICAL**: Always commit and push changes immediately. The live app deploys directly from GitHub:

```bash
git add <files>
git commit -m "Description"
git push
```

### Session State Safety

Always use `.get()` with default values when accessing session state to prevent KeyErrors on Streamlit Cloud:

```python
# GOOD
st.session_state.get('state_filters', [])

# BAD - causes KeyError on first load
st.session_state.state_filters
```

### Column Mapping

The system supports flexible column name variations. Users don't need exact column names - the auto-detection handles common variations like:
- Last Name: "last", "lastname", "last_name", "surname", "family name"
- First Name: "first", "firstname", "first_name", "given name"
- Institution: "institution", "facility", "organization", "hospital", "clinic"

### Result Structure

Each match returns:
- All provider details (name, NPI, credentials, gender, etc.)
- All addresses (main address, practice locations, endpoints)
- Taxonomy information (specialty descriptions, licenses)
- Original input data (prefixed with `input_`)
- Search criteria used to find the match

Multiple rows are created if a provider has multiple addresses, ensuring no location data is lost.

## Data Source

All NPI data comes from the CMS National Plan and Provider Enumeration System (NPPES) NPI Registry API:
- Base URL: `https://npiregistry.cms.hhs.gov/api/`
- API Version: 2.1
- No authentication required
- Rate limiting: Small delay (0.1s) between pagination requests

## File Privacy

All file processing happens locally (when run locally) or in Streamlit Cloud's isolated environment. Files are never permanently stored on any server.
