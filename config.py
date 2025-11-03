# Configuration for column name mapping
# Maps standard field names to possible column name variations

COLUMN_MAPPINGS = {
    'last_name': [
        'last', 'lastname', 'last_name', 'last name',
        'surname', 'family name', 'familyname', 'family_name',
        'lname', 'l_name'
    ],
    'first_name': [
        'first', 'firstname', 'first_name', 'first name',
        'given name', 'givenname', 'given_name',
        'fname', 'f_name'
    ],
    'institution_name': [
        'institution', 'institution_name', 'institution name',
        'facility', 'facility_name', 'facilityname', 'facility name',
        'organization', 'organization_name', 'organizationname', 'organization name',
        'org', 'org_name', 'orgname', 'org name',
        'hospital', 'hospital_name', 'hospitalname', 'hospital name',
        'clinic', 'clinic_name', 'clinicname', 'clinic name',
        'practice', 'practice_name', 'practicename', 'practice name'
    ],
    'city': [
        'city', 'city_name', 'cityname', 'city name',
        'municipality', 'town'
    ],
    'state': [
        'state', 'state_name', 'statename', 'state name',
        'st', 'province', 'region'
    ],
    'zip': [
        'zip', 'zipcode', 'zip_code', 'zip code',
        'postal', 'postalcode', 'postal_code', 'postal code',
        'postcode', 'post_code', 'post code'
    ]
}

# Required fields - at least one of these must be present
REQUIRED_FIELDS = ['last_name']

def normalize_column_name(column_name: str) -> str:
    """Normalize column name to lowercase and remove extra spaces/underscores"""
    # Handle None or non-string types
    if not isinstance(column_name, str) or not column_name:
        return ""
    # Convert to lowercase, replace underscores/spaces with single space, strip
    normalized = column_name.lower().replace('_', ' ').replace('-', ' ')
    # Remove multiple spaces
    normalized = ' '.join(normalized.split())
    return normalized

def auto_detect_columns(df_columns: list) -> dict:
    """
    Automatically detect which columns in the dataframe match our standard fields.
    Returns a dict mapping standard field names to actual column names in the dataframe.

    Args:
        df_columns: List of column names from the uploaded dataframe

    Returns:
        dict: {standard_field_name: actual_column_name} for detected matches
    """
    detected = {}

    # Normalize all dataframe column names for comparison
    # Skip None or non-string column names
    normalized_df_columns = {
        normalize_column_name(col): col
        for col in df_columns
        if col is not None and isinstance(col, str)
    }

    # Check each standard field
    for standard_field, variations in COLUMN_MAPPINGS.items():
        # Check each variation
        for variation in variations:
            normalized_variation = normalize_column_name(variation)
            if normalized_variation in normalized_df_columns:
                # Found a match - store the actual column name from the dataframe
                detected[standard_field] = normalized_df_columns[normalized_variation]
                break  # Stop checking variations once we find a match

    return detected

def validate_required_fields(detected_columns: dict) -> tuple:
    """
    Validate that required fields are present.

    Args:
        detected_columns: Dict of detected column mappings

    Returns:
        tuple: (is_valid: bool, missing_fields: list)
    """
    missing = []
    for required_field in REQUIRED_FIELDS:
        if required_field not in detected_columns:
            missing.append(required_field)

    is_valid = len(missing) == 0
    return is_valid, missing