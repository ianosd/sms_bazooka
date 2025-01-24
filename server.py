#!/usr/bin/env python3

import requests
from bottle import route, run, post, request, response, hook, get
from concurrent.futures import ThreadPoolExecutor
from threading import Lock, Thread
import time
from uuid import uuid4, UUID
from enum import Enum
import pickle

from datetime import datetime

class SMSRequest:
    def __init__(self,request_id, messages, status):
        self.id = request_id
        self.messages = messages
        self.status = status
        self.message_reports = []

class Status(Enum):
    RECEIVED = "Received"
    SUCCESS = "Success"
    FAILURE = "Failure"

sms_requests = {}
sms_requests_lock = Lock()

# the decorator
def enable_cors(fn):
    def _enable_cors(*args, **kwargs):
        # set CORS headers
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token'

        if request.method != 'OPTIONS':
            # actual request; reply with the actual response
            return fn(*args, **kwargs)

    return _enable_cors

thePassword = "dc51sa9"
@route('/sms_request', method=['OPTIONS', 'POST'] )
@enable_cors
def submit_sms_request():
    try:
        if request.json["pwd"] != thePassword:
            response.status = 404
            return
        messages = request.json["messages"]
    except:
        response.status = 400
        return 

    return {"id": str(add_request(messages))}

@route('/sms_request/<sms_request_id_str:>/status', method=['OPTIONS', 'POST'])
@enable_cors
def get_status(sms_request_id_str):
    try:
        if request.json["pwd"] != thePassword:
            response.status = 404
            return

        sms_request_id = UUID(sms_request_id_str)
        return {
            "status": sms_requests[sms_request_id].status.value,
            "message_reports": sms_requests[sms_request_id].message_reports
        }
    except ValueError:
        response.status = 400

@route('/message_reports', method=['OPTIONS', 'POST'])
@enable_cors
def get_message_reports():
    try:
        if request.json["pwd"] != thePassword:
            response.status = 404
            return
    except:
        response.status = 400
        return
    message_reports = []
    with open(sent_messages_file, "rb") as f:
        while True:
            try:
                report = pickle.load(f)
                report["datetime"] = report["datetime"].strftime("%d/%m/%Y %H:%M:%S")
                message_reports.insert(0, report)
            except EOFError:
                break
        return {'message_reports': message_reports}

@route('/credit', method=['POST', 'OPTIONS'])
@enable_cors
def get_credit():
    try:
        if request.json["pwd"] != thePassword:
            response.status = 404
            return
    except:
        response.status = 400
        return
    api_response = requests.post(smslink_url, params={"mode": "Credit"}, json=sms_link_auth)
    try:
        return {"messages": api_response.json()["credit"]}
    except:
        response.status = 400

def add_request(data):
    request_id = uuid4()
    sms_request = SMSRequest(request_id, data, Status.RECEIVED)

    with sms_requests_lock:
        sms_requests[request_id] = sms_request

    executor.submit(process_request, sms_request)
    return request_id

def process_request(sms_request): 
    print("Start processing {}".format(sms_request.id))
    message_reports = []
    for message in sms_request.messages:
        result = send_sms(message["to"], message["message"])
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

sent_messages_file = "sent_messages.p"
smslink_url = "https://secure.smslink.ro/sms/gateway/communicate/json.php"
sms_link_auth = {
        "connection_id":"",
        "password":"",
}

def send_sms(number, message):
    sent_data = {
        "to": number,
        "message": message
    }
    sent_data.update(sms_link_auth)

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
    run(host="127.0.0.1", port=8001)
