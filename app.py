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

st.info("""
**Data Source:** This tool searches the [CMS National Plan and Provider Enumeration System (NPPES) NPI Registry](https://npiregistry.cms.hhs.gov/),
a publicly available database maintained by the Centers for Medicare & Medicaid Services (CMS).
All data is retrieved using the official [NPI Registry API](https://npiregistry.cms.hhs.gov/api-page).
""")

st.divider()

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