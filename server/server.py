"""
   Copyright 2018 InfAI (CC SES)

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
"""

from flask import Flask,request
from flask_sqlalchemy import SQLAlchemy
import os
from flask_restful import Api
from flask_migrate import Migrate
from . import api 
import logging
from time import strftime
import traceback
from datetime import datetime
from threading import Timer
import requests
import base64
from requests.auth import HTTPBasicAuth
import yaml
import json
from flask_restful_swagger_2 import Api

app = Flask(__name__)
app.logger.addHandler(logging.StreamHandler())
app.logger.setLevel(logging.INFO)
app_api = Api(app, api_version='0.0', api_spec_url='/doc', host='sepl.infai.org:8088')
app_api.add_resource(api.Measurements, '/measurements')
app_api.add_resource(api.Measurement, '/measurement/<string:id>')
app_api.add_resource(api.Aggregation, '/measurement/<string:id>/<string:action>')

if __name__ == '__main__':
    if os.environ["DEBUG"] == "true":
        app.run(debug=True,host='0.0.0.0')
    else:
        app.run(debug=False, host='0.0.0.0')