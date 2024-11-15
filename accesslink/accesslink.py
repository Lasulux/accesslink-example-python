#!/usr/bin/env python

from . import endpoints
from .oauth2 import OAuth2Client
import pandas as pd

AUTHORIZATION_URL = "https://flow.polar.com/oauth2/authorization"
ACCESS_TOKEN_URL = "https://polarremote.com/v2/oauth2/token"
ACCESSLINK_URL = "https://www.polaraccesslink.com/v3"


class AccessLink(object):
    """Wrapper class for Polar Open AccessLink API v3"""

    def __init__(self, client_id, client_secret, redirect_url=None):
        if not client_id or not client_secret:
            raise ValueError("Client id and secret must be provided.")

        self.oauth = OAuth2Client(url=ACCESSLINK_URL,
                                  authorization_url=AUTHORIZATION_URL,
                                  access_token_url=ACCESS_TOKEN_URL,
                                  redirect_url=redirect_url,
                                  client_id=client_id,
                                  client_secret=client_secret)

        self.users = endpoints.Users(oauth=self.oauth)
        self.pull_notifications = endpoints.PullNotifications(oauth=self.oauth)
        self.training_data = endpoints.TrainingData(oauth=self.oauth)
        self.physical_info = endpoints.PhysicalInfo(oauth=self.oauth)
        self.daily_activity = endpoints.DailyActivity(oauth=self.oauth)

    @property
    def authorization_url(self):
        """Get the authorization url for the client"""
        return self.oauth.get_authorization_url()

    def get_access_token(self, authorization_code):
        """Request access token for a user.
        :param authorization_code: authorization code received from authorization endpoint.
        """
        return self.oauth.get_access_token(authorization_code)

    def get_exercises(self, access_token, data=None):
        return self.oauth.get(endpoint="/exercises", access_token=access_token, data=data)

    def get_sleep(self, access_token):
        return self.oauth.get(endpoint="/users/sleep/", access_token=access_token)
    
    def get_recharge(self, access_token):
        return self.oauth.get(endpoint="/users/nightly-recharge/", access_token=access_token)

    def get_userdata(self, user_id,access_token):
        return self.oauth.get(endpoint="/users/"+ str(user_id), access_token= access_token)
    
    def get_exercise_heart_rate(self, user_id,access_token):
        try:
            trainingdatatransaction = self.training_data.create_transaction(user_id=user_id,access_token=access_token)
            if not trainingdatatransaction:
                print("create_transaction returned empty.")
                return None
            resource_urls = trainingdatatransaction.list_exercises()["exercises"]
            heartrate_samples = []
            i = 0
            for url in resource_urls:
                exercise_heart_rate_sample = trainingdatatransaction.get_samples(url + "/samples/0")
                heartrate_samples.append(exercise_heart_rate_sample)
                exercise_id = url.split("/")[-1]
                exercise_heart_rate_sample["user_id"] = user_id
                exercise_heart_rate_sample["exercise_id"] = exercise_id
                print("Exercise found " + str(i) + " : " + str(url)) 
                i = i + 1
            return heartrate_samples
        except Exception as e:
            print("Error in get_exercise_heart_rate: " + str(e))
            return None
        
        
    def get_continuous_heart_rate(self, user_id,access_token,date_list):
        # TODO: iterate trhough dates, handle exceptions (no data for that day)
        try:
            response = self.oauth.get(endpoint="/users/continuous-heart-rate/2024-11-06"  , access_token= access_token)
            
            if response:
                # TODO: user id adding? parse results
                return response
            else:
                print("No continuous-heart-rate available for the given date range")
                return None
        except Exception as e:
            print("Error in get_continuous_heart_rate: " + str(e))
            return None

    def get_activity(self, user_id,access_token):
        transaction = self.daily_activity.create_transaction(user_id=user_id,access_token=access_token)
        
        if not transaction:
            print("create_transaction returned empty.")
            return None,None

        resource_urls = transaction.list_activities()["activity-log"]
        activity_summaries = []
        steptimeseries = []

        i = 0
        for url in resource_urls:
            activity_summary = transaction.get_activity_summary(url)
            activity_summaries.append(activity_summary)
            step_samples = transaction.get_step_samples(url)
            step_samples["user_id"] = user_id
            step_samples["activity_id"] = url.split("/")[-1]
            steptimeseries.append(step_samples)
            print("Activity summary found" + str(i) + ":" + str(url)) 
            i = i + 1

        # transaction.commit()
        return activity_summaries, steptimeseries

