#!/usr/bin/env python3

import requests
from bottle import route, run, request, response
from concurrent.futures import ThreadPoolExecutor
from threading import Lock, Thread
import time
from uuid import uuid4, UUID
from enum import Enum
import pickle
import subprocess
import os
import re

from datetime import datetime, timedelta

# Read connection ID and password from environment variables
SMS_LINK_CONNECTION_ID = os.getenv("SMS_LINK_CONNECTION_ID")
SMS_LINK_PASSWORD = os.getenv("SMS_LINK_PASSWORD")
SMS_BAZOOKA_PASSWORD = os.getenv("SMS_BAZOOKA_PASSWORD")
SMS_BAZOOKA_PRIVKEY = os.getenv("SMS_BAZOOKA_PRIVKEY", None)
SMS_BAZOOKA_CHAIN = os.getenv("SMS_BAZOOKA_CHAIN", None)

# Ensure the environment variables are set
if not SMS_LINK_CONNECTION_ID or not SMS_LINK_PASSWORD or not SMS_BAZOOKA_PASSWORD:
    raise ValueError("Environment variables SMS_LINK_CONNECTION_ID, SMS_LINK_PASSWORD, SMS_BAZOOKA_PASSWORD must be set.")

# Create the configuration dynamically
sms_link_auth = {
    "connection_id": SMS_LINK_CONNECTION_ID,
    "password": SMS_LINK_PASSWORD,
}

pwd2authData = {SMS_BAZOOKA_PASSWORD: sms_link_auth}

sent_messages_file = "sent_messages.p"
smslink_url = "https://secure.smslink.ro/sms/gateway/communicate/json.php"

sms_requests = {}
sms_requests_lock = Lock()

class SMSRequest:
    def __init__(self,request_id, messages, status, auth_data):
        self.id = request_id
        self.messages = messages
        self.status = status
        self.message_reports = []
        self.auth_data = auth_data

class Status(Enum):
    RECEIVED = "Received"
    SUCCESS = "Success"
    FAILURE = "Failure"

# the decorator
def enable_cors(fn):
    def _enable_cors(*args, **kwargs):
        # set CORS headers
        response.headers['Access-Control-Allow-Origin'] = 'https://ionutgoesforawalk.xyz'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token'

        if request.method != 'OPTIONS':
            # actual request; reply with the actual response
            return fn(*args, **kwargs)

    return _enable_cors


def inject_sms_link_auth(fn):
    def decorated_fn(*args, **kwargs):
        sms_link_auth = pwd2authData.get(request.json.get("pwd"))
        if sms_link_auth is None:
            response.status = 404
        else:
            try:
                return fn(sms_link_auth, *args, **kwargs)
            except:
                response.status = 400
    return decorated_fn

@route('/sms_request', method=['OPTIONS', 'POST'] )
@enable_cors
@inject_sms_link_auth
def submit_sms_request(sms_link_auth):
    return {"id": str(add_request(request.json["messages"], sms_link_auth))}

@route('/sms_request/<sms_request_id_str:>/status', method=['OPTIONS', 'POST'])
@enable_cors
@inject_sms_link_auth
def get_status(sms_link_auth, sms_request_id_str):
    try:
        sms_request_id = UUID(sms_request_id_str)
        queried_request = sms_requests.get(sms_request_id)

        if queried_request is None or not (queried_request.auth_data is sms_link_auth):
            response.status = 404
            return

        return {
            "status": queried_request.status.value,
            "message_reports": queried_request.message_reports
        }
    except ValueError:
        response.status = 400

# TODO this just returns all messages this is an issue if there really are multiple users
@route('/message_reports', method=['OPTIONS', 'POST'])
@enable_cors
@inject_sms_link_auth
def get_message_reports(sms_link_auth):
    message_reports = []
    with open(sent_messages_file, "rb") as f:
        while True:
            try:
                report = pickle.load(f)
                if datetime.today() - report["datetime"] > timedelta(days=356):
                    continue
                report["datetime"] = report["datetime"].strftime("%d/%m/%Y %H:%M:%S")
                message_reports.insert(0, report)
            except EOFError:
                break
        return {'message_reports': message_reports}


@route('/credit', method=['POST', 'OPTIONS'])
@enable_cors
@inject_sms_link_auth
def get_credit(sms_link_auth):
    try:
        api_response = requests.post(smslink_url, params={"mode": "Credit"}, json=sms_link_auth)
        return {"messages": api_response.json()["credit"]}
    except:
        response.status = 400

def add_request(data, auth_data):
    request_id = uuid4()
    sms_request = SMSRequest(request_id, data, Status.RECEIVED, auth_data)

    with sms_requests_lock:
        sms_requests[request_id] = sms_request

    executor.submit(process_request, sms_request)
    return request_id

def process_request(sms_request): 
    print("Start processing {}".format(sms_request.id))
    message_reports = []
    for message in sms_request.messages:
        result = send_sms(message["to"], message["message"], sms_request.auth_data)
        if not result.is_ok:
            message_reports.append({"to": message["to"], "message": message["message"], "sent": False, "failure_reason": result.err_str})
        else:
            message_reports.append(dict(sent=True, **message))

        with open(sent_messages_file, "ab") as f:
            pickle.dump(dict(datetime=datetime.now(), **message_reports[-1]), f)

    sms_request.message_reports = message_reports 
    if any(not report["sent"] for report in sms_request.message_reports):
        sms_request.status = Status.FAILURE
    else:
        sms_request.status = Status.SUCCESS

    print("Finished processing {}".format(sms_request.id))

def send_sms(number, message, auth_data):
    sent_data = {
        "to": number,
        "message": message
    }
    sent_data.update(auth_data)

    print("Sending request to SMSLink...")
    api_response = requests.request("POST", smslink_url, json=sent_data)
    print("Done! Response from SMSLink: {}".format(api_response.text))
    if not api_response.ok:
        return Result.error("SMSLink returned {}".format(api_response.status_code))
    
    try:
        json_resp = api_response.json()
    except:
        return Result.error("Bad response content")

    if json_resp["response_type"] == "MESSAGE":
        return Result.ok(json_resp["message_id"])
    elif json_resp["response_type"] == "ERROR":
        return Result.error(json_resp["response_message"])

class Result:
    @staticmethod
    def ok(value):
        result = Result()
        result._is_ok = True
        result._value = value
        return result

    @staticmethod
    def error(string):
        result = Result()
        result._is_ok = False
        result._err_string = string
        return result

    @property
    def is_ok(self):
        return self._is_ok

    @property
    def value(self):
        if not self._is_ok:
            raise Exception()
        return self._value

    @property
    def err_str(self):
        if self._is_ok:
            raise Exception()
        return self._err_string

with ThreadPoolExecutor(max_workers=1) as executor:
    run(host="0.0.0.0", port=8001, server='gunicorn', reloader=1, debug=1,
            keyfile=SMS_BAZOOKA_PRIVKEY, certfile=SMS_BAZOOKA_CHAIN)   
