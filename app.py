import streamlit as st
import pandas as pd
from npi_utils import process_dataframe
from config import auto_detect_columns, validate_required_fields, COLUMN_MAPPINGS
import io

# --- Streamlit App Configuration ---
st.set_page_config(
    page_title="NPI Automation Tool",
    page_icon="✨",
    layout="centered",
    initial_sidebar_state="auto"
)

# --- Main App UI ---
st.title("NPI Automation Tool")
st.write("""
This tool helps you find National Provider Identifier (NPI) numbers for healthcare providers.
Upload a CSV file with provider information, map the columns, and get back a file enriched with NPI data.
""")

# Attribution
st.markdown("""
<small>
Developed by <a href="https://www.linkedin.com/in/joeklimovitsky/" target="_blank">Joe Klimovitsky</a>
</small>
""", unsafe_allow_html=True)

st.info("""
**Data Source:** This tool searches the [CMS National Plan and Provider Enumeration System (NPPES) NPI Registry](https://npiregistry.cms.hhs.gov/),
a publicly available database maintained by the Centers for Medicare & Medicaid Services (CMS).
All data is retrieved using the official [NPI Registry API](https://npiregistry.cms.hhs.gov/api-page).

**Privacy:** Your uploaded files are processed entirely in your browser session and are never stored on any server.
All data remains on your device.
""")

st.divider()

# --- Instructions ---
with st.expander("📋 How to Use This Tool", expanded=False):
    st.markdown("""
    ### Step 1: Prepare Your CSV File
    Your CSV file should contain provider information with at least one of the following columns:

    **For Individual Providers:**
    - **Last Name** (REQUIRED) - Provider's last name
    - **First Name** (optional) - Provider's first name
    - **City** (optional) - City where provider practices
    - **State** (optional) - State abbreviation (e.g., CA, NY, TX)
    - **ZIP Code** (optional) - 5-digit ZIP code

    **For Organizations/Facilities:**
    - **Institution Name** (REQUIRED) - Name of the facility or organization
    - **State** (optional) - State abbreviation
    - **City** (optional) - City location

    ### Step 2: Column Name Flexibility
    The tool automatically detects column names. You can use any of these variations (case-insensitive):

    **Last Name:** `last`, `lastname`, `last_name`, `surname`, `family name`, `lname`

    **First Name:** `first`, `firstname`, `first_name`, `given name`, `fname`

    **Institution:** `institution`, `facility`, `organization`, `hospital`, `clinic`, `practice` (with or without `_name`)

    **City:** `city`, `municipality`, `town`

    **State:** `state`, `st`, `province`

    **ZIP Code:** `zip`, `zipcode`, `postal`, `postalcode`

    ### Step 3: Upload and Process
    1. Upload your CSV file
    2. The tool will auto-detect your columns
    3. Verify or adjust the column mappings
    4. Click "Process File" to search the NPI registry
    5. Download the results with NPI numbers and additional provider information

    ### Tips for Best Results
    - **More information = better matches**: Include first name, city, and state when available
    - **Last name only works**: The tool will find matches even with minimal information
    - **Missing data is OK**: Leave cells empty if you don't have that information
    - **Broad searches are limited**: Last-name-only searches return a maximum of 10 results per provider
    """)

st.divider()

# --- Search Mode Toggle ---
search_mode = st.radio(
    "Select Search Mode:",
    ["Manual Search", "Bulk Upload (CSV)"],
    horizontal=True
)

st.divider()

if search_mode == "Manual Search":
    # --- Manual Search Form ---
    st.write("### Manual NPI Search")
    st.write("Enter provider information to search for NPI numbers. You can add multiple providers.")

    # State mapping: full name to abbreviation
    US_STATES = {
        "": "",
        "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
        "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "Florida": "FL", "Georgia": "GA",
        "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA",
        "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
        "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS", "Missouri": "MO",
        "Montana": "MT", "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ",
        "New Mexico": "NM", "New York": "NY", "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH",
        "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
        "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT",
        "Virginia": "VA", "Washington": "WA", "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
        "District of Columbia": "DC", "Puerto Rico": "PR"
    }

    # Initialize session state for manual entries
    if 'manual_entries' not in st.session_state:
        st.session_state.manual_entries = [{}]

    # Add entry button
    if st.button("➕ Add Another Provider"):
        st.session_state.manual_entries.append({})

    # Display entry forms
    manual_data = []
    for idx, entry in enumerate(st.session_state.manual_entries):
        # Create header with remove button
        col_header1, col_header2 = st.columns([4, 1])
        with col_header1:
            st.markdown(f"**Provider #{idx + 1}**")
        with col_header2:
            if len(st.session_state.manual_entries) > 1:
                if st.button("🗑️", key=f"remove_{idx}", help="Remove this provider"):
                    st.session_state.manual_entries.pop(idx)
                    st.rerun()

        # Compact form layout - 3 columns
        col1, col2, col3 = st.columns(3)

        with col1:
            last_name = st.text_input(
                "Last Name*",
                value=entry.get('last_name', ''),
                key=f"last_name_{idx}"
            )
            city = st.text_input(
                "City",
                value=entry.get('city', ''),
                key=f"city_{idx}"
            )

        with col2:
            first_name = st.text_input(
                "First Name",
                value=entry.get('first_name', ''),
                key=f"first_name_{idx}"
            )
            # State dropdown
            state_name = st.selectbox(
                "State",
                options=list(US_STATES.keys()),
                index=0,
                key=f"state_{idx}"
            )
            state_code = US_STATES[state_name]

        with col3:
            institution_name = st.text_input(
                "Institution Name",
                value=entry.get('institution_name', ''),
                key=f"institution_name_{idx}"
            )
            zip_code = st.text_input(
                "ZIP Code",
                value=entry.get('zip', ''),
                key=f"zip_{idx}",
                placeholder="5-digit"
            )

        st.divider()

        # Store the data with state code
        entry_data = {
            'last_name': last_name,
            'first_name': first_name,
            'institution_name': institution_name,
            'city': city,
            'state': state_code,  # Use state code for API
            'zip': zip_code
        }
        manual_data.append(entry_data)

    # Search button for manual entries
    if st.button("🔍 Search NPI Registry", type="primary"):
        # Validate that at least one entry has required data
        valid_entries = [
            entry for entry in manual_data
            if entry.get('last_name') or entry.get('institution_name')
        ]

        if not valid_entries:
            st.error("Please provide at least a Last Name or Institution Name for one provider.")
        else:
            # Create DataFrame from manual entries
            manual_df = pd.DataFrame(valid_entries)

            # Remove empty string values (replace with None)
            manual_df = manual_df.replace('', None)

            # Create mappings (identity mapping since columns already match)
            manual_mappings = {col: col for col in manual_df.columns if col in manual_df.columns}

            try:
                with st.spinner("Searching the NPI registry... This may take a few moments."):
                    # Progress bar
                    progress_bar = st.progress(0)

                    def update_progress(fraction):
                        progress_bar.progress(fraction)

                    # Process the dataframe
                    results_df = process_dataframe(manual_df, manual_mappings, progress_callback=update_progress)

                    if len(results_df) > 0:
                        st.success(f"Processing complete! Found {len(results_df)} total matches.")
                        st.write("### Results")
                        st.dataframe(results_df, use_container_width=True, height=600)

                        # --- Download Button ---
                        @st.cache_data
                        def convert_df_to_csv(df_to_convert):
                            return df_to_convert.to_csv(index=False).encode('utf-8')

                        csv_output = convert_df_to_csv(results_df)

                        st.download_button(
                            label="Download Results as CSV",
                            data=csv_output,
                            file_name="npi_results.csv",
                            mime="text/csv",
                        )
                    else:
                        st.warning("No matches found for the provided information. Try adjusting your search criteria.")

            except Exception as e:
                st.error(f"An error occurred during processing: {e}")

else:  # Bulk Upload (CSV) mode
    # --- File Uploader ---
    uploaded_file = st.file_uploader("Upload your CSV file", type="csv")

    if uploaded_file is not None:
        try:
            # Read the uploaded CSV file
            df = pd.read_csv(uploaded_file)
            st.success("File uploaded successfully!")

            # Display a preview of the uploaded data
            st.write("### Preview of your data:")
            st.dataframe(df.head())

            # --- Auto-detect columns ---
            detected_columns = auto_detect_columns(df.columns.tolist())
            is_valid, missing_fields = validate_required_fields(detected_columns)

            # Show detection results
            if detected_columns:
                st.success(f"Auto-detected {len(detected_columns)} column(s)")
                for standard_field, actual_column in detected_columns.items():
                    st.write(f"  - **{standard_field}**: `{actual_column}`")

            if not is_valid:
                st.warning(f"Missing required field(s): {', '.join(missing_fields)}")

            # --- Column Mapping ---
            st.write("### Map your columns")
            st.write("Auto-detected columns are pre-selected. You can change them or map additional fields manually.")

            # Define the fields for the NPI search
            field_labels = {
                "last_name": "Provider Last Name (REQUIRED)",
                "first_name": "Provider First Name (optional)",
                "institution_name": "Institution Name (optional)",
                "city": "City (optional)",
                "state": "State (optional)",
                "zip": "ZIP Code (optional)"
            }

            column_options = ["-"] + list(df.columns)
            user_mappings = {}

            for key, label in field_labels.items():
                # Find the index of the auto-detected column, or default to 0 ("-")
                default_index = 0
                if key in detected_columns:
                    detected_col = detected_columns[key]
                    if detected_col in column_options:
                        default_index = column_options.index(detected_col)

                user_mappings[key] = st.selectbox(label, options=column_options, index=default_index)

            # --- Processing Logic ---
            if st.button("Process File"):
                # Create a new dataframe with standardized column names
                try:
                    mapped_df = pd.DataFrame()
                    final_mappings = {}

                    for key, selected_col in user_mappings.items():
                        if selected_col != "-":
                            mapped_df[key] = df[selected_col]
                            final_mappings[key] = selected_col

                    # Check for required field (last_name)
                    if 'last_name' not in final_mappings:
                        st.error("You must map the 'Last Name' field to proceed. It is required.")
                    else:
                        with st.spinner("Searching the NPI registry... This may take a few moments."):
                            # Progress bar
                            progress_bar = st.progress(0)

                            def update_progress(fraction):
                                progress_bar.progress(fraction)

                            # Process the dataframe
                            results_df = process_dataframe(mapped_df, final_mappings, progress_callback=update_progress)

                            st.success(f"Processing complete! Found {len(results_df)} total matches.")
                            st.write("### Results")
                            st.dataframe(results_df, use_container_width=True, height=600)

                            # --- Download Button ---
                            @st.cache_data
                            def convert_df_to_csv(df_to_convert):
                                # IMPORTANT: Cache the conversion to prevent computation on every rerun
                                return df_to_convert.to_csv(index=False).encode('utf-8')

                            csv_output = convert_df_to_csv(results_df)

                            st.download_button(
                                label="Download Results as CSV",
                                data=csv_output,
                                file_name="npi_results.csv",
                                mime="text/csv",
                            )
                except Exception as e:
                    st.error(f"An error occurred during processing: {e}")

        except Exception as e:
            st.error(f"Error reading or processing file: {e}")
    else:
        st.info("Please upload a CSV file to begin.")