#!/usr/bin/env python
from __future__ import print_function
import platform
if platform.system() == 'Windows':
    from asyncio.windows_events import NULL
from genericpath import exists
from pickle import NONE

import requests
from flask import Flask, request, redirect, render_template

from utils import load_config, save_config
from accesslink import AccessLink
import pandas as pd
from typing import Dict, List
import re
import isodate
import tqdm

CALLBACK_PORT = 5000
CALLBACK_ENDPOINT = "/oauth2_callback"

CONFIG_FILENAME = "config_custom.yml"
TOKEN_FILENAME = "multiple_user_tokens.yml"
SETTINGS_FILENAME = "settings.yml"

REDIRECT_URL = "http://localhost:{}{}".format(CALLBACK_PORT, CALLBACK_ENDPOINT)

KEY_BLACKLIST = ["nights", "access_token", "heart_rate_samples"]

config = load_config(CONFIG_FILENAME)
settings = load_config(SETTINGS_FILENAME)

accesslink = AccessLink(client_id=config['client_id'],
                        client_secret=config['client_secret'],
                        redirect_url=REDIRECT_URL,
                        verbose=config['verbose'])
app = Flask(__name__)

@app.route("/")
def index():
    status=request.args.get("status")
    return render_template("index.html", userid = config["client_id"], status=status)

@app.route("/data")
def data():
    tokens = token_db()
    alldata = []    
    i=0
    tqdm.tqdm.write(f"Found {len(tokens['tokens'])} users. Starting to collect data.")

    date_list = extract_dates(start = settings["start_date"], end = settings["end_date"])
    tqdm.tqdm.write(f"Date list: {date_list}")
    if len(date_list) == 0:
        tqdm.tqdm.write("No dates to fetch continuous heart rate data for!")
    elif len(date_list) > 31:
        tqdm.tqdm.write("Too many dates to fetch continuous heart rate data for. Might get blocked by API regulations... (warning at 31 days)")

    for item in tqdm.tqdm(tokens["tokens"], desc="Processing users"):
        tqdm.tqdm.write(f"Checking user: {str(i+1)}. User ID: {item['user_id']}")
        i+=1
        if item == None:
            continue
        # exercisedata = accesslink.get_exercises(access_token=item["access_token"], data={"samples": True})
        sleepdata = accesslink.get_sleep(access_token=item["access_token"])
        rechargedata = accesslink.get_recharge(access_token=item["access_token"])
        userdata = accesslink.get_userdata(user_id=item["user_id"], access_token=item["access_token"])
        activitydata, steptimeseries = accesslink.get_activity(user_id=item["user_id"],access_token=item["access_token"])
        if len(date_list) > 0:
            continous_heart_rate = accesslink.get_continuous_heart_rate(user_id=item["user_id"],access_token=item["access_token"],date_list=date_list)
        else:
            continous_heart_rate = []
        exercise_summary, exercise_heart_rate = accesslink.get_exercise_data(user_id=item["user_id"],access_token=item["access_token"])
        
        alldata.append( {   "exercise_summary": exercise_summary,
                            "sleepdata": sleepdata,
                            "recharge": rechargedata,
                            "userdata": userdata,
                            "activitydata": activitydata,
                            "coninous_heart_rate": continous_heart_rate,
                            "exercise_heart_rate": exercise_heart_rate,
                            "steptimeseries": steptimeseries
                            })
        if alldata["activitydata"] == None or len(alldata["activitydata"]) == 0 and i >= 5:
            tqdm.tqdm.write("No activity data found for multiple users... Maybe data collection was called too frequently? One users data can be only downloaded every 10 minutes. If still no data is found, check the user's data in the Polar Flow web app. Its also possible that the daily limit of API calls has been reached.")
    
    tqdm.tqdm.write("Compiling data to Excel files...")
    # Convert the collected data to a DataFrame
    df = pd.DataFrame(alldata)
    # Save the DataFrame to an Excel file
    df.to_excel("data.xlsx", index=False)
    user_df = add_dict_columns_to_dataframe(df["userdata"],"userdata")
    user_df.to_excel("users_data.xlsx", index=False)

    activity_df = add_dict_columns_to_dataframe(df["activitydata"],"activitydata")
    
    if "created" in activity_df.columns:
        activity_df = extract_date_time(activity_df, 'created')

    activity_df.to_excel("activity_data.xlsx", index=False)

    exercises_df = add_dict_columns_to_dataframe(df["exercise_summary"],"exercise_summary")
    exercises_df.to_excel("exercise_summary.xlsx", index=False)

    if 'duration' in exercises_df.columns:
        exercises_df['duration_hhmmss'] = exercises_df['duration'].apply(convert_duration_to_hhmmss)
    if 'start-time' in exercises_df.columns:
        exercises_df = extract_date_time(exercises_df, 'start-time')
    if 'polar-user' in exercises_df.columns:
        exercises_df['user_id'] = exercises_df['polar-user'].apply(extract_user_id)
    exercises_df['exercise_id'] = exercises_df['id']
    columns_to_keep = ['user_id','exercise_id', 'start_date', 'start_time', 'duration_hhmmss', 'calories','distance','heart-rate:_average','heart-rate:_maximum','sport','fat-percentage','carbohydrate-percentage','protein-percentage','training-load-pro:_cardio-load','training-load-pro:_cardio-load-interpretation','device-id','upload-time']
    exercises_df = exercises_df.filter(items=columns_to_keep)


    exercises_df.to_excel("exercise_summary_filtered.xlsx", index=False)
    sleep_df = add_dict_columns_to_dataframe(df["sleepdata"],"sleepdata")
    sleep_df.to_excel("sleep_data.xlsx", index=False)
    if len(date_list) > 0:
        continous_heart_rate_df = add_dict_columns_to_dataframe(df["coninous_heart_rate"],"coninous_heart_rate")
        continous_heart_rate_df.to_excel("continous_heart_rate_data.xlsx", index=False)

    steptimeseries = add_dict_columns_to_dataframe(df["steptimeseries"],"steptimeseries")
    steptimeseries.to_excel("steptimeseries.xlsx", index=False)

    # if we are not running the app just exit
    return
    # return render_template("data.html", alldata = alldata)

@app.route(CALLBACK_ENDPOINT)
def callback():
    """Callback for OAuth2 authorization request

    Saves the user's id and access token to a file.
    """

    #
    # Get authorization from the callback request parameters
    #
    authorization_code = request.args.get("code")

    #
    # Get an access token for the user using the authorization code.
    #
    # The authorization code is only valid for 10 minutes, so the access token
    # should be fetched immediately after the authorization step.
    #
    token_response = accesslink.get_access_token(authorization_code)

    #
    # Save the user's id and access token to the configuration file.
    #

    user_id = token_response["x_user_id"]
    accesstoken = token_response["access_token"]

    usertokens = token_db()

    usertokens["tokens"] = remove_oldtokens(array = usertokens["tokens"], newuserid= user_id)
    newtoken = {"user_id": user_id, "access_token":accesstoken}
    usertokens["tokens"].append(newtoken)
    save_config(usertokens, TOKEN_FILENAME)

    #
    # Register the user as a user of the application.
    # This must be done before the user's data can be accessed through AccessLink.
    #
    try:
        accesslink.users.register(access_token=accesstoken)
    except requests.exceptions.HTTPError as err:
        # Error 409 Conflict means that the user has already been registered for this client.
        # That error can be ignored in this example.
        if err.response.status_code != 409:
            return redirect("/?status=duplicatetokens")

    return redirect("/?status=ok")  

def add_dict_columns_to_dataframe(dict_list,original_name, df=pd.DataFrame(None), delete_original=False, new_df=True):
    
    if new_df:
        df=pd.DataFrame(None)
    
    if not len(dict_list)==0 and not isinstance(dict_list[0],Dict):
        for user_dict_list in dict_list:
            if user_dict_list:
                inner_df = add_dict_columns_to_dataframe(user_dict_list, original_name, df, delete_original, new_df)
                df = pd.concat([inner_df, df], ignore_index=True)
        return df
    
    # Get unique keys from all dictionaries
    all_keys = set(key for mydict in dict_list for key in mydict.keys())
    # Iterate through each dictionary in the list
    for mydict in dict_list:
        # Add new columns for each key in the current dictionary
        for key in mydict.keys():
            # Check if the column already exists
            if isinstance(mydict[key], Dict):
                for inner_key in mydict[key].keys():
                    fieldname = f"{key}:_{inner_key}"
                    if fieldname not in df.columns:
                        df[fieldname] = [mydict[key].get(inner_key) for _ in range(len(df))]
                continue
            if isinstance(mydict[key], List):
                if bool(mydict[key]) and isinstance(mydict[key][0], Dict):
                    for inner_key in mydict[key][0].keys():
                        fieldname = f"{key}:_{inner_key}"
                        if fieldname not in df.columns:
                            df[fieldname] = [mydict[key][0].get(inner_key) for _ in range(len(df))]
                    continue
            if key not in df.columns and key not in KEY_BLACKLIST:
                # df[f"{original_name}_{key}"] = [mydict.get(key) for _ in range(len(df))]
                df[key] = [mydict.get(key) for _ in range(len(df))]

    # for key in all_keys:
    if original_name == "coninous_heart_rate":
        polar_users=[]
        dates=[]
        heart_rate_samples=[]
        sample_times=[]
        for mydict in dict_list:
            #we get a dict for each user
            number_of_rows_for_this_user = len(mydict["heart_rate_samples"])
            polar_users += [  mydict["polar_user"]] * number_of_rows_for_this_user
            dates += [mydict["date"]] * number_of_rows_for_this_user
            heart_rate_samples_list_for_user = []
            sample_time_list_for_user  = []
            for item in mydict["heart_rate_samples"]:
                heart_rate_samples_list_for_user.append(item["heart_rate"])
                sample_time_list_for_user.append(item["sample_time"])
            heart_rate_samples+= heart_rate_samples_list_for_user
            sample_times+= sample_time_list_for_user
        df["polar_user"] = polar_users
        df["date"] = dates
        df["heart_rate_samples:_heart_rate"] = heart_rate_samples
        df["heart_rate_samples:_sample_time"] = sample_times
    elif original_name == "steptimeseries":
        interval=[]
        date=[]
        steptimesamples =[]
        sample_times =[]
        user_id =[]
        activity_id =[]
        for mydict in dict_list:
            #we get a dict for each user
            number_of_rows_for_this_user = len(mydict["samples"])
            interval += [mydict["interval"]] * number_of_rows_for_this_user
            date += [mydict["date"]] * number_of_rows_for_this_user
            user_id += [mydict["user_id"]] * number_of_rows_for_this_user
            activity_id += [mydict["activity_id"]] * number_of_rows_for_this_user
            samples_steps =[]
            samples_time =[]
            for item in mydict["samples"]:
                if item and "steps" in item.keys() and "time" in item.keys():
                    samples_steps.append(item["steps"])
                    samples_time.append(item["time"])
                else:
                    samples_steps.append(0)
                    samples_time.append(0)
            steptimesamples+= samples_steps
            sample_times+= samples_time
        df["interval"] = interval
        df["date"] = date
        df["user_id"] = user_id
        df["activity_id"] = activity_id
        df["samples:_steps"] = steptimesamples
        df["samples:_time"] = sample_times
    else:
        for key in df.columns:
            value_list = []
            for mydict in dict_list:
                if ':_' in key and bool(mydict[key.split(':_')[0]]):
                    inner_key = key.split(':_')[1]
                    if isinstance(mydict[key.split(':_')[0]], Dict):
                        value_list.append(mydict.get(key.split(':_')[0]).get(inner_key))
                        continue
                    if isinstance(mydict[key.split(':_')[0]], List):
                        for item in mydict[key.split(':_')[0]]:
                            value_list.append(item.get(inner_key))
                    continue
                # if we want multiple samples here in one row:
                value_list.append(mydict.get(key))
            df[key] = value_list
            pass
    
    if delete_original:
        # Delete the original column
        df.drop(columns=[original_name], inplace=True)

    return df

def remove_oldtokens(array , newuserid):
    res = []
    for item in array:
        if item == None:
            del item
            continue
        useritem = item["user_id"]
        usertoken = item["access_token"]
        if useritem != newuserid:
            res.append({"user_id": useritem,
                      "access_token":usertoken})
    return res

def convert_duration_to_hhmmss(duration):
    try:
        # Parse the ISO 8601 duration
        parsed_duration = isodate.parse_duration(duration)
        # Convert to total seconds
        total_seconds = int(parsed_duration.total_seconds())
        # Format as HH:MM:SS
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02}:{minutes:02}:{seconds:02}"
    except Exception as e:
        print(f"Error converting duration: {e}")
        return None

def extract_user_id(url):
    match = re.search(r'/users/(\d+)$', url)
    if match:
        return match.group(1)
    else:
        return None

def extract_date_time(df, column_name):
    # Convert the column to datetime
    df[column_name] = pd.to_datetime(df[column_name])
    # Extract date and time
    df['start_date'] = df[column_name].dt.date
    df['start_time'] = df[column_name].dt.time
    # Convert date and time to string format
    df['start_date'] = df['start_date'].astype(str)
    df['start_time'] = df['start_time'].astype(str)
    return df

def extract_dates(start, end):
    date_list = []
    start_date = pd.to_datetime(start)
    end_date = pd.to_datetime(end)
    while start_date <= end_date:
        date_list.append(start_date.strftime('%Y-%m-%d'))
        start_date += pd.DateOffset(days=1)
    return date_list

def token_db():
    usertokens = None
    if exists(TOKEN_FILENAME):
        usertokens = load_config(TOKEN_FILENAME)
    if usertokens == None:
        usertokens = {"tokens" : []}
    return usertokens

def main():
    # print("Navigate to http://localhost:{port}/ for authorization.\n".format(port=CALLBACK_PORT))
    # app.run(host='localhost', port=CALLBACK_PORT)
    # do data collection
    data()
    print("Data collection done.")

if __name__ == "__main__":
    main()