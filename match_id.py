import pandas as pd

# Load datasets
def load_data(account_df_filename='participant_email_account - Sheet1.csv', account_birthdate_filename='id_dateofbirth.csv',api_df=None):
    """Load account, birthdate, and API data from CSV/Excel files."""
    account_df = pd.read_csv(account_df_filename, usecols=['ID', 'sex', 'height', 'weight'],
                             dtype={'ID': str})
    account_birthdate = pd.read_csv(account_birthdate_filename, sep='\t', usecols=['Subject ID', 'date_of_birth'])
    if api_df is None:
        api_df = pd.read_excel('users_data.xlsx', usecols=['polar_user_id', 'gender', 'weight', 'height', 'birthdate'])
    return account_df, account_birthdate, api_df

# Standardize and clean data
def clean_data(account_df, account_birthdate, api_df):
    """Standardize column names, gender format, and clean Subject ID."""
    account_df.rename(columns={'ID': 'account_id', 'sex': 'gender'}, inplace=True)
    account_df['gender'] = account_df['gender'].map({'M': 'MALE', 'F': 'FEMALE'})

    # Clean 'Subject ID' in account_birthdate by removing 'sub-'
    account_birthdate['Subject ID'] = account_birthdate['Subject ID'].str.replace('sub-', '', regex=True)
    account_birthdate.rename(columns={'Subject ID': 'account_id', 'date_of_birth': 'birthdate'}, inplace=True)

    # Convert birthdate columns to datetime and extract only Year-Month
    account_birthdate['birthdate'] = pd.to_datetime(account_birthdate['birthdate']).dt.to_period('M')
    api_df['birthdate'] = pd.to_datetime(api_df['birthdate']).dt.to_period('M')

    return account_df, account_birthdate, api_df

# Merge account_df with birthdate and then with api_df
def merge_data(account_df, account_birthdate, api_df):
    """Merge account data with birthdate and then API data."""
    # Merge account_df with account_birthdate on account_id
    account_merged = account_df.merge(account_birthdate, on='account_id', how='left')

    # Merge with api_df on gender, weight, height, and birthdate (Year-Month only)
    final_merged_df = account_merged.merge(api_df, on=['gender', 'weight', 'height', 'birthdate'], how='left',
                                           indicator=True)

    # Find unmatched entries
    unmatched_entries = final_merged_df[final_merged_df['_merge'] == 'left_only'].drop(columns=['_merge'])

    return final_merged_df, unmatched_entries

# Main execution
if __name__ == "__main__":
    # Load and clean data
    account_df, account_birthdate, api_df = load_data()
    account_df, account_birthdate, api_df = clean_data(account_df, account_birthdate, api_df)

    # Merge data
    merged_df, unmatched_entries = merge_data(account_df, account_birthdate, api_df)

    print("\n🔄 Merged DataFrame:")
    print(merged_df.head())

    print("\n🔍 Unmatched Entries:")
    print(unmatched_entries)
