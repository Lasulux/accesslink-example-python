import pandas as pd
from datetime import timedelta
import re


# Function to load and prepare data
def load_and_prepare_data(file_path):
    df = pd.read_csv(file_path, index_col=0)
    df = df[['id', 'start-time', 'start-time-utc-offset', 'duration', 'calories', 'heart-rate']]
    df = df.rename(columns={'id': 'exercise_id'})
    return df


# Function to parse date and time
def convert_start_time(df):
    df['start-time'] = pd.to_datetime(df['start-time'])
    df['adjusted-time'] = df['start-time'] + df['start-time-utc-offset'].apply(lambda x: timedelta(minutes=x))
    df['date'] = df['adjusted-time'].dt.date
    df['start_time'] = df['adjusted-time'].dt.time
    return df


# Function to parse ISO 8601 format of duration into H:MM:SS
def parse_duration(duration):
    match = re.match(r'PT((?P<hours>\d+)H)?((?P<minutes>\d+)M)?((?P<seconds>\d+(\.\d+)?)S)?', duration)
    if not match:
        return "0:00:00"
    hours = int(match.group('hours')) if match.group('hours') else 0
    minutes = int(match.group('minutes')) if match.group('minutes') else 0
    seconds = float(match.group('seconds')) if match.group('seconds') else 0
    return f"{hours}:{int(minutes):02}:{int(seconds):02}"


# Function to parse duration in the dataframe
def process_duration_column(df):
    df['duration'] = df['duration'].apply(parse_duration)
    return df


# Function to split heart rate max and average
def split_heart_rate_column(df):
    df['heart_rate_average'] = df['heart-rate'].apply(lambda x: eval(x)['average'] if isinstance(x, str) else x['average'])
    df['heart_rate_max'] = df['heart-rate'].apply(lambda x: eval(x)['maximum'] if isinstance(x, str) else x['maximum'])
    return df


# Function to reorder columns
def finalize_columns(df):
    return df[['exercise_id', 'date', 'start_time', 'duration', 'heart_rate_average', 'heart_rate_max', 'calories']]


def get_exercise_summary():
    exercise_file = 'exercise_summary.csv'  # equivalent to 'pd.Dataframe(exercise_summary) in multiple_account_web_app.py

    df = load_and_prepare_data(exercise_file)
    df = convert_start_time(df)
    df = process_duration_column(df)
    df = split_heart_rate_column(df)
    df = finalize_columns(df)
    return df


# Main Script
if __name__ == "__main__":
    exercise_summary = get_exercise_summary()
