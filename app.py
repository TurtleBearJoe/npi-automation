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
col_title, col_help = st.columns([4, 1])
with col_title:
    st.title("NPI Automation Tool")
    st.caption("Find National Provider Identifier (NPI) numbers for healthcare providers")
with col_help:
    with st.popover("ℹ️ Help"):
        st.markdown("""
        **Required:** Last Name OR Institution Name

        **Optional:** First Name, City, State, ZIP

        **Data Source:** [CMS NPPES NPI Registry](https://npiregistry.cms.hhs.gov/)

        **Privacy:** Files processed locally, never stored on server
        """)

st.caption("Developed by [Joe Klimovitsky](https://www.linkedin.com/in/joeklimovitsky/)")

# Initialize session state for taxonomy preferences
if 'saved_taxonomies' not in st.session_state:
    st.session_state.saved_taxonomies = []

# --- File Uploader ---
uploaded_file = st.file_uploader("Upload your CSV file", type="csv")

if uploaded_file is not None:
    try:
        # Read the uploaded CSV file
        df = pd.read_csv(uploaded_file)
        st.success("File uploaded successfully!")

        # Display a compact preview of the uploaded data
        with st.expander("👁️ Preview Data", expanded=False):
            st.dataframe(df.head(3), use_container_width=True)

        # --- Auto-detect columns ---
        detected_columns = auto_detect_columns(df.columns.tolist())
        is_valid, missing_fields = validate_required_fields(detected_columns)

        # Show detection results - single line summary with human-readable names
        if detected_columns:
            field_name_map = {
                "last_name": "Last Name",
                "first_name": "First Name",
                "institution_name": "Institution Name",
                "city": "City",
                "state": "State",
                "zip": "ZIP Code"
            }
            detected_names = [field_name_map.get(k, k) for k in detected_columns.keys()]
            st.success(f"Auto-detected: {', '.join(detected_names)}")

        if not is_valid:
            st.warning(f"Missing required field(s): {', '.join(missing_fields)}")

        # --- Column Mapping ---
        st.write("**Map Your Columns**")

        # Define the fields for the NPI search
        field_labels = {
            "last_name": "Last Name*",
            "first_name": "First Name",
            "institution_name": "Institution",
            "city": "City",
            "state": "State",
            "zip": "ZIP"
        }

        column_options = ["-"] + list(df.columns)
        user_mappings = {}

        # Compact 3-column layout for mapping
        col1, col2, col3 = st.columns(3)

        with col1:
            for key in ["last_name", "first_name"]:
                default_index = 0
                if key in detected_columns and detected_columns[key] in column_options:
                    default_index = column_options.index(detected_columns[key])
                user_mappings[key] = st.selectbox(
                    field_labels[key],
                    options=column_options,
                    index=default_index,
                    key=f"map_{key}"
                )

        with col2:
            for key in ["institution_name", "city"]:
                default_index = 0
                if key in detected_columns and detected_columns[key] in column_options:
                    default_index = column_options.index(detected_columns[key])
                user_mappings[key] = st.selectbox(
                    field_labels[key],
                    options=column_options,
                    index=default_index,
                    key=f"map_{key}"
                )

        with col3:
            for key in ["state", "zip"]:
                default_index = 0
                if key in detected_columns and detected_columns[key] in column_options:
                    default_index = column_options.index(detected_columns[key])
                user_mappings[key] = st.selectbox(
                    field_labels[key],
                    options=column_options,
                    index=default_index,
                    key=f"map_{key}"
                )

        # --- Taxonomy Filter Section ---
        with st.expander("🏥 Filter by Taxonomy Keywords (Optional)", expanded=False):
            st.caption("Enter keywords to filter specialties (e.g., 'surgery', 'ortho', 'neuro')")

            col_load, col_manual = st.columns(2)

            with col_load:
                uploaded_tax_csv = st.file_uploader("📁 Load Keywords", type="json", key="tax_upload_csv")
                if uploaded_tax_csv:
                    import json
                    tax_data = json.load(uploaded_tax_csv)
                    st.session_state.saved_taxonomies = tax_data.get('taxonomies', [])
                    st.success(f"Loaded {len(st.session_state.saved_taxonomies)} keywords")

            with col_manual:
                manual_tax_input_csv = st.text_area(
                    "✏️ Keywords (one per line)",
                    height=80,
                    placeholder="surgery\northo\nneuro\ninternal\ncardio",
                    key="tax_input_csv"
                )
                if st.button("Add to Filter", key="add_tax_csv"):
                    if manual_tax_input_csv:
                        new_taxes = [t.strip() for t in manual_tax_input_csv.split('\n') if t.strip()]
                        st.session_state.saved_taxonomies.extend(new_taxes)
                        st.session_state.saved_taxonomies = list(set(st.session_state.saved_taxonomies))
                        st.success(f"Added {len(new_taxes)} keywords")

            if st.session_state.saved_taxonomies:
                st.write(f"**Active Keywords** ({len(st.session_state.saved_taxonomies)}): Matches any taxonomy containing these terms")
                tax_cols = st.columns(3)
                for idx, tax in enumerate(st.session_state.saved_taxonomies):
                    with tax_cols[idx % 3]:
                        st.caption(f"• {tax}")

                col_clear, col_download = st.columns(2)
                with col_clear:
                    if st.button("🗑️ Clear All", key="clear_tax_csv"):
                        st.session_state.saved_taxonomies = []
                        st.rerun()
                with col_download:
                    import json
                    tax_json = json.dumps({'taxonomies': st.session_state.saved_taxonomies}, indent=2)
                    st.download_button(
                        "💾 Download Keywords",
                        data=tax_json,
                        file_name="taxonomy_keywords.json",
                        mime="application/json",
                        key="download_tax_csv"
                    )

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

                        # Process the dataframe with taxonomy filter
                        taxonomy_filter = st.session_state.saved_taxonomies if st.session_state.saved_taxonomies else None
                        results_df = process_dataframe(mapped_df, final_mappings, progress_callback=update_progress, taxonomy_filter=taxonomy_filter)

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