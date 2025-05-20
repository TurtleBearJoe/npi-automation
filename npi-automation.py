import pandas as pd
import requests
import time
from typing import List, Dict, Set
import json
import re
import os
import unicodedata

class TextCleaner:
    @staticmethod
    def clean_text(text: str) -> str:
        """Clean text by removing extra spaces, special characters, and trimming"""
        if pd.isna(text):
            return ""
        # Convert to string if not already
        text = str(text)
        # Normalize unicode characters (é -> e, ó -> o, etc.)
        text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII')
        # Remove multiple spaces and trim
        text = ' '.join(text.split())
        # Remove leading/trailing spaces
        return text.strip()
    
    @staticmethod
    def clean_zip(zip_code: str) -> str:
        """Clean ZIP code by removing extra characters and taking only first 5 digits"""
        if pd.isna(zip_code):
            return ""
        zip_code = str(zip_code)
        # Remove any non-digit characters
        zip_code = ''.join(filter(str.isdigit, zip_code))
        # Take only first 5 digits
        return zip_code[:5]

class NPILookup:
    def __init__(self):
        self.base_url = "https://npiregistry.cms.hhs.gov/api/"
        self.version = "2.1"
        self.text_cleaner = TextCleaner()
        # List of US states for validation
        self.us_states = set([
            'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
            'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
            'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
            'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
            'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
            'DC', 'PR'
        ])

    def is_us_address(self, state: str, zip_code: str) -> bool:
        """Check if address is in the US"""
        if not state or not zip_code:
            return False
        state = state.upper()
        return state in self.us_states and len(self.text_cleaner.clean_zip(zip_code)) == 5

    def search_npi(self, **kwargs) -> List[Dict]:
        """Search for NPI numbers based on provided criteria."""
        try:
            # Clean all text inputs
            cleaned_params = {}
            for k, v in kwargs.items():
                if v and not pd.isna(v):
                    if k == 'postal_code':
                        cleaned_params[k] = self.text_cleaner.clean_zip(v)
                    else:
                        cleaned_params[k] = self.text_cleaner.clean_text(v)

            # Skip US address validation if searching by organization name
            if ('state' in cleaned_params and 'postal_code' in cleaned_params and 
                not 'organization_name' in cleaned_params and
                not self.is_us_address(cleaned_params['state'], cleaned_params['postal_code'])):
                return []
            
            params = {
                'version': self.version,
                'limit': 200,
                'pretty': True,
                **cleaned_params
            }

            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if not isinstance(data, dict) or 'result_count' not in data:
                print(f"Warning: Unexpected API response format for parameters {cleaned_params}")
                return []
            
            if data['result_count'] > 0:
                return data['results']
            return []

        except Exception as e:
            print(f"Warning: Error searching with parameters {cleaned_params}: {str(e)}")
            return []

    def search_with_organization_name(self, institution_name: str, state: str = None) -> List[Dict]:
        """
        Search specifically for an organization by name and optionally state.
        This function is optimized for institutional searches.
        """
        try:
            # Prepare search parameters
            search_params = {
                'organization_name': institution_name,
                'enumeration_type': 'org'  # Specifically search for organizations
            }
            
            # Add state if provided
            if state and not pd.isna(state):
                search_params['state'] = state
                
            # Perform the search
            results = self.search_npi(**search_params)
            
            # If no results with exact parameters, try a broader search
            if not results:
                # Try with just the organization name
                results = self.search_npi(organization_name=institution_name, enumeration_type='org')
            
            return results
            
        except Exception as e:
            print(f"Warning: Error searching for institution {institution_name}: {str(e)}")
            return []

    def search_with_multiple_combinations(self, provider_data: Dict) -> List[Dict]:
        """
        Search using multiple combinations of the provided data.
        Updated to handle both individual providers and organizations.
        """
        all_matches = []
        seen_npis = set()

        # Check if this is an institution search
        if 'institution_name' in provider_data and provider_data.get('institution_name'):
            # This is an institutional search
            institution_matches = self.search_with_organization_name(
                provider_data.get('institution_name'),
                provider_data.get('state')
            )
            
            # Process institution matches
            for match in institution_matches:
                npi = match['number']
                if npi not in seen_npis:
                    seen_npis.add(npi)
                    all_matches.append({
                        'search_criteria': f"institution_name: {provider_data.get('institution_name')}",
                        **match
                    })
            
            # Return early with institution matches if any were found
            if all_matches:
                return all_matches

        # If this is not an institution search or no institution matches were found,
        # fall back to the original search strategy for individual providers
        
        # Define search combinations from most specific to least specific for individuals
        search_strategies = [
            # Strategy 1: First name, last name, city, and state (most specific)
            {
                'required_fields': ['first_name', 'last_name', 'city', 'state'],
                'params': {
                    'first_name': provider_data.get('first_name'),
                    'last_name': provider_data.get('last_name'),
                    'city': provider_data.get('city'),
                    'state': provider_data.get('state')
                },
                'verify': lambda m, p: (
                    m['basic'].get('first_name', '').upper() == p['first_name'].upper() and
                    m['basic'].get('last_name', '').upper() == p['last_name'].upper() and
                    any(a.get('city', '').upper() == p['city'].upper() and 
                        a.get('state', '').upper() == p['state'].upper() 
                        for a in m['addresses'])
                )
            },
            # Strategy 2: First name, last name, and state
            {
                'required_fields': ['first_name', 'last_name', 'state'],
                'params': {
                    'first_name': provider_data.get('first_name'),
                    'last_name': provider_data.get('last_name'),
                    'state': provider_data.get('state')
                },
                'verify': lambda m, p: (
                    m['basic'].get('first_name', '').upper() == p['first_name'].upper() and
                    m['basic'].get('last_name', '').upper() == p['last_name'].upper() and
                    any(a.get('state', '').upper() == p['state'].upper() 
                        for a in m['addresses'])
                )
            },
            # Strategy 3: Last name, city, and state
            {
                'required_fields': ['last_name', 'city', 'state'],
                'params': {
                    'last_name': provider_data.get('last_name'),
                    'city': provider_data.get('city'),
                    'state': provider_data.get('state')
                },
                'verify': lambda m, p: (
                    m['basic'].get('last_name', '').upper() == p['last_name'].upper() and
                    any(a.get('city', '').upper() == p['city'].upper() and 
                        a.get('state', '').upper() == p['state'].upper() 
                        for a in m['addresses'])
                )
            },
            # Strategy 4: Last name and state
            {
                'required_fields': ['last_name', 'state'],
                'params': {
                    'last_name': provider_data.get('last_name'),
                    'state': provider_data.get('state')
                },
                'verify': lambda m, p: (
                    m['basic'].get('last_name', '').upper() == p['last_name'].upper() and
                    any(a.get('state', '').upper() == p['state'].upper() 
                        for a in m['addresses'])
                )
            },
            # Strategy 5: First name and last name only, then verify locations in full record
            {
                'required_fields': ['first_name', 'last_name'],
                'params': {
                    'first_name': provider_data.get('first_name'),
                    'last_name': provider_data.get('last_name')
                },
                'verify': lambda m, p: (
                    # First verify name match
                    m['basic'].get('first_name', '').upper() == p['first_name'].upper() and
                    m['basic'].get('last_name', '').upper() == p['last_name'].upper() and
                    # Then check all possible locations for city+state or state match
                    (
                        # Check for city + state match in any address type
                        (p.get('city') and any(
                            a.get('city', '').upper() == p['city'].upper() and 
                            a.get('state', '').upper() == p['state'].upper()
                            for a in (
                                m.get('addresses', []) +
                                m.get('practiceLocations', []) +
                                m.get('endpoints', [])
                            )
                        ))
                        or
                        # If no city+state match, check for state match only
                        (p.get('state') and any(
                            a.get('state', '').upper() == p['state'].upper()
                            for a in (
                                m.get('addresses', []) +
                                m.get('practiceLocations', []) +
                                m.get('endpoints', [])
                            )
                        ))
                    )
                )
            }
        ]

        for strategy in search_strategies:
            # Check if we have all required fields for this strategy
            if not all(provider_data.get(field) for field in strategy['required_fields']):
                continue

            # Remove None or empty values from params
            search_params = {k: v for k, v in strategy['params'].items() if v}
            
            matches = self.search_npi(**search_params)
            
            # Process matches
            strategy_matches = []
            for match in matches:
                npi = match['number']
                
                # Only include matches that satisfy the current strategy's criteria
                if npi not in seen_npis and strategy['verify'](match, provider_data):
                    seen_npis.add(npi)
                    strategy_matches.append({
                        'search_criteria': str(search_params),
                        **match
                    })

            # If this strategy found any matches, use only these matches and stop searching
            if strategy_matches:
                all_matches.extend(strategy_matches)
                break

            # Add small delay between searches
            time.sleep(0.1)

        return all_matches

def detect_provider_type(df: pd.DataFrame) -> str:
    """
    Detect whether the CSV contains individual providers or institutions
    based on the columns present in the dataframe.
    """
    # Check for institution name column
    if any(col in df.columns for col in ['institution_name', 'organization_name', 'facility_name', 'org_name']):
        return 'institution'
    
    # Check for last name + first name columns (common for individual providers)
    if 'last_name' in df.columns and 'first_name' in df.columns:
        return 'individual'
    
    # If we can't clearly determine, check for more columns
    institution_indicators = ['facility', 'hospital', 'clinic', 'center', 'institution', 'organization']
    
    # Look for any column names that might indicate institutions
    for col in df.columns:
        for indicator in institution_indicators:
            if indicator.lower() in col.lower():
                return 'institution'
    
    # Default to individual if we can't determine
    return 'individual'

def load_config():
    """Load configuration from config.json"""
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            
            # Check if this is the old config format (required_fields as list)
            if isinstance(config.get('required_fields'), list):
                print("Converting old config format to new format...")
                # Convert to new format
                old_required = config['required_fields']
                config['required_fields'] = {
                    'individual': old_required,
                    'institution': ['institution_name']
                }
                
                # Save back the updated config
                with open(config_path, 'w') as fw:
                    json.dump(config, fw, indent=4)
                    
                print("Config updated to new format.")
            
            return config
    except FileNotFoundError:
        print(f"Error: config.json not found at {config_path}")
        exit(1)
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in config.json")
        exit(1)



def get_column_name(df: pd.DataFrame, possible_names: List[str]) -> str:
    """Find the actual column name from a list of possible names"""
    for name in possible_names:
        if name in df.columns:
            return name
    return None

def map_columns(df: pd.DataFrame, config: Dict) -> pd.DataFrame:
    """Map DataFrame columns to standardized names based on config"""
    column_mappings = config['column_mappings']
    mapped_df = df.copy()
    
    # Create mapping of actual column names to standardized names
    column_map = {}
    found_columns = []
    missing_columns = []
    
    for standard_name, possible_names in column_mappings.items():
        actual_name = get_column_name(df, possible_names)
        if actual_name:
            column_map[actual_name] = standard_name
            found_columns.append(f"{actual_name} -> {standard_name}")
        else:
            missing_columns.append(standard_name)
    
    # Print column mapping information
    print("\nFound columns:")
    for col in found_columns:
        print(f"  {col}")
    
    print("\nInput CSV columns:")
    for col in df.columns:
        print(f"  {col}")
    
    # Rename columns
    mapped_df = mapped_df.rename(columns=column_map)
    
    return mapped_df


def process_csv(input_file: str, output_file: str):
    """
    Process input CSV and create output CSV with NPI matches.
    Results are written to file as they are found.
    Modified to handle both individual providers and institutions.
    """
    try:
        # Load config
        config = load_config()
        
        # Create error log file and progress tracking file
        log_file = os.path.splitext(output_file)[0] + '_errors.log'
        progress_file = os.path.splitext(output_file)[0] + '_progress.json'
        
        # Read input CSV
        df = pd.read_csv(input_file)
        
        # Map columns to standardized names
        df = map_columns(df, config)
        
        # Detect provider type based on columns
        provider_type = detect_provider_type(df)
        print(f"\nDetected provider type: {provider_type}")
        
        # Determine required fields based on provider type
        required_fields = config['required_fields'][provider_type]
        
        # Verify required columns exist
        missing_columns = [col for col in required_fields if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {', '.join(missing_columns)}\n"
                           f"Please ensure your CSV contains columns for: {', '.join(required_fields)}")

        # Load progress if exists
        start_idx = 0
        if os.path.exists(progress_file):
            try:
                with open(progress_file, 'r') as f:
                    progress_data = json.load(f)
                    start_idx = progress_data.get('last_processed_row', 0) + 1
                    print(f"Resuming from row {start_idx + 1}")
            except Exception as e:
                print(f"Warning: Could not load progress file: {str(e)}")

        npi_lookup = NPILookup()
        total_matches = 0
        error_count = 0

        # Track NPIs we've already seen
        seen_npis = set()
        
        # Process each row starting from last processed row
        for idx, row in df.iloc[start_idx:].iterrows():
            try:
                provider_id = row.get('institution_name', row.get('last_name', f"Row {idx+1}"))
                print(f"Processing {provider_id} ({idx + 1}/{len(df)})...")
                
                # Prepare provider data based on provider type
                provider_data = {}
                
                if provider_type == 'institution':
                    provider_data['institution_name'] = row['institution_name']
                    # Add optional fields if available
                    if 'state' in df.columns:
                        provider_data['state'] = row.get('state', '')
                else:
                    # Individual provider fields
                    provider_data['last_name'] = row['last_name']
                    if 'first_name' in df.columns:
                        provider_data['first_name'] = row.get('first_name', '')
                    if 'city' in df.columns:
                        provider_data['city'] = row.get('city', '')
                    if 'state' in df.columns:
                        provider_data['state'] = row.get('state', '')

                matches = npi_lookup.search_with_multiple_combinations(provider_data)
                
                if matches:
                    batch_results = []
                    for match in matches:
                        try:
                            # Skip if we've already seen this NPI
                            if match['number'] in seen_npis:
                                continue
                            
                            seen_npis.add(match['number'])
                            addresses_to_process = (
                                [(addr, 'main') for addr in match['addresses']] +
                                [(loc, 'practice') for loc in match.get('practiceLocations', [])] +
                                [(endpoint, 'endpoint') for endpoint in match.get('endpoints', [])]
                            )
                            
                            # Only process the first address (most relevant one)
                            if addresses_to_process:
                                addr, addr_type = addresses_to_process[0]
                                
                                # Determine result structure based on provider type
                                if provider_type == 'institution':
                                    result = {
                                        # Input data
                                        'input_institution_name': provider_data['institution_name'],
                                        'input_state': provider_data.get('state', ''),
                                        'search_criteria_used': match['search_criteria'],
                                        
                                        # NPI number
                                        'npi': match['number'],
                                        
                                        # Address information
                                        'address_type': addr_type,
                                        'address': addr.get('address_1', ''),
                                        'city': addr.get('city', ''),
                                        'state': addr.get('state', ''),
                                        'zip': addr.get('postal_code', ''),
                                        'phone': addr.get('telephone_number', ''),
                                        'fax': addr.get('fax_number', ''),
                                        
                                        # Organization information
                                        'organization_name': match['basic'].get('organization_name', ''),
                                        'organizational_subpart': match['basic'].get('organizational_subpart', ''),
                                        'authorized_official_first_name': match['basic'].get('authorized_official_first_name', ''),
                                        'authorized_official_last_name': match['basic'].get('authorized_official_last_name', ''),
                                        'authorized_official_title': match['basic'].get('authorized_official_title', ''),
                                        'status': match['basic'].get('status', ''),
                                        
                                        # Taxonomy information
                                        'taxonomy_desc': match['taxonomies'][0].get('desc', '') if match.get('taxonomies') else '',
                                        'taxonomy_group': match['taxonomies'][0].get('taxonomy_group', '') if match.get('taxonomies') else '',
                                    }
                                else:
                                    # Individual provider
                                    result = {
                                        # Input data
                                        'input_last_name': provider_data['last_name'],
                                        'input_first_name': provider_data.get('first_name', ''),
                                        'input_city': provider_data.get('city', ''),
                                        'input_state': provider_data.get('state', ''),
                                        'search_criteria_used': match['search_criteria'],
                                        
                                        # NPI number
                                        'npi': match['number'],
                                        
                                        # Address information
                                        'address_type': addr_type,
                                        'address': addr.get('address_1', ''),
                                        'city': addr.get('city', ''),
                                        'state': addr.get('state', ''),
                                        'zip': addr.get('postal_code', ''),
                                        'phone': addr.get('telephone_number', ''),
                                        'fax': addr.get('fax_number', ''),
                                        
                                        # Basic information
                                        'first_name': match['basic'].get('first_name', ''),
                                        'last_name': match['basic'].get('last_name', ''),
                                        'middle_name': match['basic'].get('middle_name', ''),
                                        'sole_proprietor': match['basic'].get('sole_proprietor', ''),
                                        'gender': match['basic'].get('gender', ''),
                                        'status': match['basic'].get('status', ''),
                                        'name_prefix': match['basic'].get('name_prefix', ''),
                                        'name_suffix': match['basic'].get('name_suffix', ''),
                                        
                                        # Taxonomy information
                                        'taxonomy_desc': match['taxonomies'][0].get('desc', '') if match.get('taxonomies') else '',
                                        'taxonomy_group': match['taxonomies'][0].get('taxonomy_group', '') if match.get('taxonomies') else '',
                                    }
                                
                                # Add endpoint specific information if it's an endpoint address
                                if addr_type == 'endpoint':
                                    result.update({
                                        'endpoint_type': addr.get('endpointType', ''),
                                        'endpoint_type_desc': addr.get('endpointTypeDescription', ''),
                                        'endpoint': addr.get('endpoint', ''),
                                        'affiliation_name': addr.get('affiliationName', ''),
                                        'content_other_desc': addr.get('contentOtherDescription', ''),
                                    })
                                
                                batch_results.append(result)

                        except Exception as e:
                            error_msg = f"Error processing match for {provider_id}: {str(e)}\n"
                            with open(log_file, 'a', encoding='utf-8') as f:
                                f.write(error_msg)
                            error_count += 1
                            continue

                    # Write batch results to file
                    if batch_results:
                        df_batch = pd.DataFrame(batch_results)
                        # If this is the first write, include headers
                        write_header = not os.path.exists(output_file)
                        df_batch.to_csv(output_file, mode='a', header=write_header, index=False)
                        
                    total_matches += len(batch_results)
                    print(f"Found {len(batch_results)} matches for {provider_id}")
                else:
                    # Log why no matches were found
                    error_msg = (f"No matches found for {provider_id}, "
                               f"Provider Type: {provider_type}, "
                               f"Data: {provider_data}\n")
                    with open(log_file, 'a', encoding='utf-8') as f:
                        f.write(error_msg)
                    print(f"No matches found for {provider_id} - see error log for details")

                # Save progress after each row
                with open(progress_file, 'w') as f:
                    json.dump({'last_processed_row': idx}, f)

            except Exception as e:
                error_msg = f"Error processing row {idx + 1} ({provider_id}): {str(e)}\n"
                with open(log_file, 'a', encoding='utf-8') as f:
                    f.write(error_msg)
                error_count += 1
                continue

        # Update summary in log file
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"\nSummary:\n")
            f.write(f"Total providers processed: {len(df)}\n")
            f.write(f"Total matches found: {total_matches}\n")
            f.write(f"Unique NPIs found: {len(seen_npis)}\n")
            f.write(f"Providers without matches: {len(df) - len(seen_npis)}\n")

        print(f"\nProcessing complete. Results saved to {output_file}")
        print(f"Found {len(seen_npis)} unique NPIs across {len(df)} providers")
        if error_count > 0:
            print(f"Encountered {error_count} errors. See {log_file} for details")

        # Clear progress file after successful completion
        if os.path.exists(progress_file):
            os.remove(progress_file)

    except Exception as e:
        print(f"Critical error processing CSV: {str(e)}")
        
        
if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    
    # Create input and output directories if they don't exist
    input_dir = os.path.join(script_dir, "input")
    output_dir = os.path.join(script_dir, "output")
    
    for directory in [input_dir, output_dir]:
        if not os.path.exists(directory):
            os.makedirs(directory)
    
    # List all CSV files in the input directory
    csv_files = [f for f in os.listdir(input_dir) if f.endswith('.csv')]
    
    if not csv_files:
        print(f"Error: No CSV files found in input directory: {input_dir}")
        print("Please place your CSV files in the 'input' folder.")
        exit(1)
    
    # Show available CSV files
    print("\nAvailable CSV files:")
    for i, file in enumerate(csv_files, 1):
        print(f"{i}. {file}")
    
    # Get user selection
    while True:
        try:
            print("\nSelect file number:")
            selection = int(input("> ").strip())
            if 1 <= selection <= len(csv_files):
                selected_file = csv_files[selection - 1]
                break
            print(f"Please enter 1-{len(csv_files)}")
        except ValueError:
            print("Enter a valid number")
    
    # Peek at the CSV file to determine if it likely contains institutions
    try:
        with open(os.path.join(input_dir, selected_file), 'r') as f:
            header = f.readline().strip()
            columns = [col.strip() for col in header.split(',')]
            
            # Check if any column name indicates institution data
            institution_indicators = ['institution', 'organization', 'facility', 'hospital', 
                                     'practice', 'clinic', 'center', 'org']
            
            has_institution_columns = any(any(indicator in col.lower() for indicator in institution_indicators) 
                                        for col in columns)
            
            if has_institution_columns:
                print("\nDetected possible institution data in this CSV.")
                print("The script will attempt to search for organizations in the NPI registry.")
            else:
                print("\nThis appears to be individual provider data.")
                print("The script will search for individual providers in the NPI registry.")
    
    except Exception as e:
        print(f"Warning: Could not analyze CSV columns: {str(e)}")
    
    # Create input and output paths and start processing
    input_file = os.path.join(input_dir, selected_file)
    base_name = os.path.splitext(selected_file)[0]
    output_file = os.path.join(output_dir, f"{base_name}_npi_{timestamp}.csv")
    
    print("\nStarting NPI lookup process...")
    process_csv(input_file, output_file)        