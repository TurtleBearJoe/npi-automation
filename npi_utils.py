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
            # Treat empty strings and NaN values as missing
            if not all(
                provider_data.get(field) and not pd.isna(provider_data.get(field))
                for field in strategy['required_fields']
            ):
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

def process_dataframe(df: pd.DataFrame, column_mappings: Dict, progress_callback=None):
    """
    Process a DataFrame to find NPI matches.
    This is a modified version of the original process_csv function.
    """
    provider_type = detect_provider_type(df)

    required_fields = {
        "individual": ["last_name"],
        "institution": ["institution_name"]
    }

    missing_columns = [col for col in required_fields[provider_type] if col not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns for {provider_type}s: {', '.join(missing_columns)}")

    npi_lookup = NPILookup()
    all_results = []
    seen_npis = set()
    total_rows = len(df)

    for idx, row in df.iterrows():
        if progress_callback:
            progress_callback(idx / total_rows)

        provider_data = {}
        if provider_type == 'institution':
            provider_data['institution_name'] = row.get('institution_name', '')
            if 'state' in df.columns:
                provider_data['state'] = row.get('state', '')
        else:
            provider_data['last_name'] = row.get('last_name', '')
            if 'first_name' in df.columns:
                provider_data['first_name'] = row.get('first_name', '')
            if 'city' in df.columns:
                provider_data['city'] = row.get('city', '')
            if 'state' in df.columns:
                provider_data['state'] = row.get('state', '')

        matches = npi_lookup.search_with_multiple_combinations(provider_data)

        if matches:
            for match in matches:
                if match['number'] in seen_npis:
                    continue

                seen_npis.add(match['number'])
                addresses_to_process = (
                    [(addr, 'main') for addr in match['addresses']] +
                    [(loc, 'practice') for loc in match.get('practiceLocations', [])] +
                    [(endpoint, 'endpoint') for endpoint in match.get('endpoints', [])]
                )

                if addresses_to_process:
                    addr, addr_type = addresses_to_process[0]

                    result = {}
                    # Add original row data to result
                    for col in df.columns:
                        result[f"input_{col}"] = row[col]

                    if provider_type == 'institution':
                        result.update({
                            'search_criteria_used': match['search_criteria'],
                            'npi': match['number'],
                            'address_type': addr_type,
                            'address': addr.get('address_1', ''),
                            'city': addr.get('city', ''),
                            'state': addr.get('state', ''),
                            'zip': addr.get('postal_code', ''),
                            'phone': addr.get('telephone_number', ''),
                            'fax': addr.get('fax_number', ''),
                            'organization_name': match['basic'].get('organization_name', ''),
                            'organizational_subpart': match['basic'].get('organizational_subpart', ''),
                            'authorized_official_first_name': match['basic'].get('authorized_official_first_name', ''),
                            'authorized_official_last_name': match['basic'].get('authorized_official_last_name', ''),
                            'authorized_official_title': match['basic'].get('authorized_official_title', ''),
                            'status': match['basic'].get('status', ''),
                            'taxonomy_desc': match['taxonomies'][0].get('desc', '') if match.get('taxonomies') else '',
                            'taxonomy_group': match['taxonomies'][0].get('taxonomy_group', '') if match.get('taxonomies') else '',
                        })
                    else: # Individual
                        result.update({
                            'search_criteria_used': match['search_criteria'],
                            'npi': match['number'],
                            'address_type': addr_type,
                            'address': addr.get('address_1', ''),
                            'city': addr.get('city', ''),
                            'state': addr.get('state', ''),
                            'zip': addr.get('postal_code', ''),
                            'phone': addr.get('telephone_number', ''),
                            'fax': addr.get('fax_number', ''),
                            'first_name': match['basic'].get('first_name', ''),
                            'last_name': match['basic'].get('last_name', ''),
                            'middle_name': match['basic'].get('middle_name', ''),
                            'sole_proprietor': match['basic'].get('sole_proprietor', ''),
                            'gender': match['basic'].get('gender', ''),
                            'status': match['basic'].get('status', ''),
                            'name_prefix': match['basic'].get('name_prefix', ''),
                            'name_suffix': match['basic'].get('name_suffix', ''),
                            'taxonomy_desc': match['taxonomies'][0].get('desc', '') if match.get('taxonomies') else '',
                            'taxonomy_group': match['taxonomies'][0].get('taxonomy_group', '') if match.get('taxonomies') else '',
                        })

                    if addr_type == 'endpoint':
                        result.update({
                            'endpoint_type': addr.get('endpointType', ''),
                            'endpoint_type_desc': addr.get('endpointTypeDescription', ''),
                            'endpoint': addr.get('endpoint', ''),
                            'affiliation_name': addr.get('affiliationName', ''),
                            'content_other_desc': addr.get('contentOtherDescription', ''),
                        })

                    all_results.append(result)

    if progress_callback:
        progress_callback(1.0)

    return pd.DataFrame(all_results)