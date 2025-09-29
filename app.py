import streamlit as st
import pandas as pd
from npi_utils import process_dataframe
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

        # --- Column Mapping ---
        st.write("### Map your columns")
        st.write("Select the columns from your file that correspond to the required fields.")

        # Define the fields required for the NPI search
        required_mappings = {
            "last_name": "Provider Last Name",
            "first_name": "Provider First Name (optional)",
            "institution_name": "Institution Name",
            "city": "City (optional)",
            "state": "State (optional, but recommended)"
        }

        column_options = ["-"] + list(df.columns)
        user_mappings = {}

        for key, label in required_mappings.items():
            user_mappings[key] = st.selectbox(label, options=column_options, index=0)

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

                if not final_mappings:
                    st.error("You must map at least one column to proceed.")
                else:
                    with st.spinner("Searching the NPI registry... This may take a few moments."):
                        # Progress bar
                        progress_bar = st.progress(0)

                        def update_progress(fraction):
                            progress_bar.progress(fraction)

                        # Process the dataframe
                        results_df = process_dataframe(mapped_df, final_mappings, progress_callback=update_progress)

                        st.success("Processing complete!")
                        st.write("### Results")
                        st.dataframe(results_df)

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