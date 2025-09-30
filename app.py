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

# --- Search Mode Toggle ---
search_mode = st.radio(
    "**Search Mode:**",
    ["Manual Search", "Bulk Upload (CSV)"],
    horizontal=True
)

if search_mode == "Manual Search":
    # --- Manual Search Form ---
    st.write("**Manual Search** - Enter provider information below")

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

    # --- Taxonomy Filter Section ---
    with st.expander("🏥 Filter by Taxonomy (Optional)", expanded=False):
        st.caption("Limit search to specific provider specialties")

        col_load, col_manual = st.columns(2)

        with col_load:
            # Load/Save taxonomy preferences
            uploaded_tax = st.file_uploader("📁 Load Saved Taxonomies", type="json", key="tax_upload")
            if uploaded_tax:
                import json
                tax_data = json.load(uploaded_tax)
                st.session_state.saved_taxonomies = tax_data.get('taxonomies', [])
                st.success(f"Loaded {len(st.session_state.saved_taxonomies)} taxonomies")

        with col_manual:
            # Manual taxonomy input
            manual_tax_input = st.text_area(
                "✏️ Manual Input (one per line)",
                height=80,
                placeholder="e.g.\nOrthopedic Surgery\nInternal Medicine"
            )
            if st.button("Add to Filter"):
                if manual_tax_input:
                    new_taxes = [t.strip() for t in manual_tax_input.split('\n') if t.strip()]
                    st.session_state.saved_taxonomies.extend(new_taxes)
                    st.session_state.saved_taxonomies = list(set(st.session_state.saved_taxonomies))  # Remove duplicates
                    st.success(f"Added {len(new_taxes)} taxonomies")

        # Display current taxonomy filter
        if st.session_state.saved_taxonomies:
            st.write(f"**Active Filter** ({len(st.session_state.saved_taxonomies)} taxonomies):")

            # Show taxonomies in columns for compact display
            tax_cols = st.columns(3)
            for idx, tax in enumerate(st.session_state.saved_taxonomies):
                with tax_cols[idx % 3]:
                    st.caption(f"• {tax}")

            col_clear, col_download = st.columns(2)
            with col_clear:
                if st.button("🗑️ Clear All"):
                    st.session_state.saved_taxonomies = []
                    st.rerun()
            with col_download:
                import json
                tax_json = json.dumps({'taxonomies': st.session_state.saved_taxonomies}, indent=2)
                st.download_button(
                    "💾 Download Filter",
                    data=tax_json,
                    file_name="taxonomy_filter.json",
                    mime="application/json"
                )

    # Search button for manual entries
    if st.button("🔍 Search NPI Registry", type="primary"):
        # Debug: Show what we're collecting
        st.write("Debug - Manual data collected:", manual_data)

        # Validate that at least one entry has required data (non-empty strings)
        valid_entries = [
            entry for entry in manual_data
            if (entry.get('last_name') and entry.get('last_name').strip()) or
               (entry.get('institution_name') and entry.get('institution_name').strip())
        ]

        st.write("Debug - Valid entries:", valid_entries)

        if not valid_entries:
            st.error("Please provide at least a Last Name or Institution Name for one provider.")
        else:
            # Create DataFrame from manual entries
            manual_df = pd.DataFrame(valid_entries)

            # Remove empty string values (replace with None)
            manual_df = manual_df.replace('', None)

            # Also handle the 'zip' column name for consistency
            if 'zip' in manual_df.columns:
                manual_df = manual_df.rename(columns={'zip': 'zip'})

            # Create mappings (identity mapping since columns already match)
            manual_mappings = {col: col for col in manual_df.columns if col in manual_df.columns}

            try:
                with st.spinner("Searching the NPI registry... This may take a few moments."):
                    # Progress bar
                    progress_bar = st.progress(0)

                    def update_progress(fraction):
                        progress_bar.progress(fraction)

                    # Process the dataframe with taxonomy filter
                    taxonomy_filter = st.session_state.saved_taxonomies if st.session_state.saved_taxonomies else None
                    results_df = process_dataframe(manual_df, manual_mappings, progress_callback=update_progress, taxonomy_filter=taxonomy_filter)

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

            # --- Taxonomy Filter Section (same as manual search) ---
            with st.expander("🏥 Filter by Taxonomy (Optional)", expanded=False):
                st.caption("Limit search to specific provider specialties")

                col_load, col_manual = st.columns(2)

                with col_load:
                    uploaded_tax_csv = st.file_uploader("📁 Load Saved Taxonomies", type="json", key="tax_upload_csv")
                    if uploaded_tax_csv:
                        import json
                        tax_data = json.load(uploaded_tax_csv)
                        st.session_state.saved_taxonomies = tax_data.get('taxonomies', [])
                        st.success(f"Loaded {len(st.session_state.saved_taxonomies)} taxonomies")

                with col_manual:
                    manual_tax_input_csv = st.text_area(
                        "✏️ Manual Input (one per line)",
                        height=80,
                        placeholder="e.g.\nOrthopedic Surgery\nInternal Medicine",
                        key="tax_input_csv"
                    )
                    if st.button("Add to Filter", key="add_tax_csv"):
                        if manual_tax_input_csv:
                            new_taxes = [t.strip() for t in manual_tax_input_csv.split('\n') if t.strip()]
                            st.session_state.saved_taxonomies.extend(new_taxes)
                            st.session_state.saved_taxonomies = list(set(st.session_state.saved_taxonomies))
                            st.success(f"Added {len(new_taxes)} taxonomies")

                if st.session_state.saved_taxonomies:
                    st.write(f"**Active Filter** ({len(st.session_state.saved_taxonomies)} taxonomies):")
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
                            "💾 Download Filter",
                            data=tax_json,
                            file_name="taxonomy_filter.json",
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