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

CALLBACK_PORT = 5000
CALLBACK_ENDPOINT = "/oauth2_callback"

CONFIG_FILENAME = "config_custom.yml"
TOKEN_FILENAME = "multiple_user_tokens.yml"

REDIRECT_URL = "http://localhost:{}{}".format(CALLBACK_PORT, CALLBACK_ENDPOINT)

KEY_BLACKLIST = ["nights", "access_token", "heart_rate_samples"]

config = load_config(CONFIG_FILENAME)

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
    for item in tokens["tokens"]:
        print("checking user: ",str(i), item["user_id"])
        i+=1
        if item == None:
            continue
        exercisedata = accesslink.get_exercises(access_token=item["access_token"], data={"samples": True})
        sleepdata = accesslink.get_sleep(access_token=item["access_token"])
        rechargedata = accesslink.get_recharge(access_token=item["access_token"])
        userdata = accesslink.get_userdata(user_id=item["user_id"], access_token=item["access_token"])
        activitydata, steptimeseries = accesslink.get_activity(user_id=item["user_id"],access_token=item["access_token"])
        continous_heart_rate = accesslink.get_continuous_heart_rate(user_id=item["user_id"],access_token=item["access_token"],date_list=["2024-11-05","2024-11-06"])
        exercise_heart_rate = accesslink.get_exercise_heart_rate(user_id=item["user_id"],access_token=item["access_token"])
        alldata.append( {"exercises": exercisedata,
                           "sleepdata": sleepdata,
                           "recharge": rechargedata,
                           "userdata": userdata,
                           "activitydata": activitydata,
                           "coninous_heart_rate": continous_heart_rate,
                           "exercise_heart_rate": exercise_heart_rate,
                           "steptimeseries": steptimeseries
                           })
        
    # Convert the collected data to a DataFrame
    df = pd.DataFrame(alldata)
    # Save the DataFrame to an Excel file
    df.to_excel("data.xlsx", index=False)

    user_df = add_dict_columns_to_dataframe(df["userdata"],"userdata")
    # TODO: TTK specific user id somehow used for joins?
    user_df.to_excel("users_data.xlsx", index=False)
    exercises_df = add_dict_columns_to_dataframe(df["exercises"],"exercises")
    exercises_df.to_excel("exercises_data.xlsx", index=False)
    sleep_df = add_dict_columns_to_dataframe(df["sleepdata"],"sleepdata")
    sleep_df.to_excel("sleep_data.xlsx", index=False)
    continous_heart_rate_df = add_dict_columns_to_dataframe(df["coninous_heart_rate"],"coninous_heart_rate")
    continous_heart_rate_df.to_excel("continous_heart_rate_data.xlsx", index=False)



    return render_template("data.html", alldata = alldata)

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
                        if isinstance(item.get(inner_key), List): # Perhaps we should implement some recursive function to deal with all the lists of dicts of lists of dicts of...
                            pass Todo fix this heart rate sample stuffff
                            inner_value_list = []
                        value_list.append(item.get(inner_key))
                continue
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

def token_db():
    usertokens = None
    if exists(TOKEN_FILENAME):
        usertokens = load_config(TOKEN_FILENAME)
    if usertokens == None:
        usertokens = {"tokens" : []}
    return usertokens

def main():
    print("Navigate to http://localhost:{port}/ for authorization.\n".format(port=CALLBACK_PORT))
    app.run(host='localhost', port=CALLBACK_PORT)

if __name__ == "__main__":
    main()