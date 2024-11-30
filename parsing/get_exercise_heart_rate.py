import pandas as pd
from datetime import datetime, timedelta
import re


# Function to load and preprocess heart rate data
def preprocess_heart_rate(file_path):
    heart_rate_data = pd.read_csv(file_path, index_col=0)
    heart_rate_data = heart_rate_data.drop(['recording-rate', 'sample-type'], axis=1)
    heart_rate_data['data'] = heart_rate_data['data'].str.split(',')
    heart_rate_data = heart_rate_data.explode('data').reset_index(drop=True)
    heart_rate_data['data'] = heart_rate_data['data'].astype(int)
    heart_rate_data = heart_rate_data[['user_id', 'exercise_id', 'data']]
    heart_rate_data = heart_rate_data.rename(columns={'data': 'heart_rate'})
    return heart_rate_data


# Function to parse duration strings into timedelta
def parse_duration(duration):
    match = re.match(r'PT((?P<hours>\d+H)?(?P<minutes>\d+M)?(?P<seconds>\d+\.?\d*S)?)', duration)
    if not match:
        return timedelta(0)  # Return zero timedelta if the format is invalid
    hours = float(match.group('hours')[:-1]) if match.group('hours') else 0
    minutes = float(match.group('minutes')[:-1]) if match.group('minutes') else 0
    seconds = float(match.group('seconds')[:-1]) if match.group('seconds') else 0
    return timedelta(hours=hours, minutes=minutes, seconds=seconds)


# Function to load and preprocess exercise data
def preprocess_exercise_data(file_path):
    exercise_data = pd.read_csv(file_path, index_col=0)
    exercise_data = exercise_data[['polar-user', 'id', 'start-time', 'start-time-utc-offset', 'duration']]
    exercise_data = exercise_data.rename(columns={'id': 'exercise_id'})
    exercise_data['user_id'] = exercise_data['polar-user'].apply(lambda x: x.split('/')[-1])
    exercise_data = exercise_data.drop('polar-user', axis=1)
    exercise_data['start-time'] = pd.to_datetime(exercise_data['start-time'])
    exercise_data['duration_timedelta'] = exercise_data['duration'].apply(parse_duration)
    exercise_data['start_time_utc_offset'] = exercise_data['start-time-utc-offset'].apply(
        lambda x: timedelta(minutes=x))
    exercise_data['adjusted_start_time'] = exercise_data['start-time'] + exercise_data['start_time_utc_offset']
    exercise_data = exercise_data.drop('start-time-utc-offset', axis=1)
    return exercise_data


# Function to generate date arrays
def generate_date_array(start, duration, step=1):
    return [start + timedelta(seconds=i) for i in range(0, int(duration.total_seconds()) + 1, step)]


# Function to add "date" and "time" columns
def add_date_to_heart_rate(heart_rate_data, exercise_data):
    exercise_data['date_array'] = exercise_data.apply(
        lambda row: generate_date_array(row['adjusted_start_time'], row['duration_timedelta']), axis=1
    )

    date_mapping = exercise_data.set_index('exercise_id')['date_array'].to_dict()
    heart_rate_data['date'] = heart_rate_data['exercise_id'].map(date_mapping).explode().reset_index(drop=True)
    heart_rate_data['date'] = pd.to_datetime(heart_rate_data['date'])

    heart_rate_data['date_only'] = heart_rate_data['date'].dt.date  # Extract date (Y-M-D)
    heart_rate_data['time_only'] = heart_rate_data['date'].dt.time  # Extract time (H-M-S)

    heart_rate_data = heart_rate_data.drop(columns=['date'])
    heart_rate_data = heart_rate_data.rename(columns={
        'date_only': 'date',
        'time_only': 'time'
    })
    return heart_rate_data


# Main function
def get_exercise_heart_rate():
    heart_rate_file = 'exercise_hr.csv'  # equivalent to pd.DataFrame(exercise_heart_rate) in multiple_account_web_app.py
    exercise_file = 'exercise_summary.csv'  # equivalent to 'pd.Dataframe(exercise_summary) in multiple_account_web_app.py

    heart_rate_data = preprocess_heart_rate(heart_rate_file)
    exercise_data = preprocess_exercise_data(exercise_file)
    heart_rate_data_with_date = add_date_to_heart_rate(heart_rate_data, exercise_data)
    print("Exercise heart rate data preprocessed.")
    return heart_rate_data_with_date


if __name__ == "__main__":
    exercise_hr = get_exercise_heart_rate()
