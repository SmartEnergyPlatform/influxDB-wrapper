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

import json
import requests
from flask import request, jsonify
from flask_restful import Resource
import os 
import server
import logging
import json 
import urllib


class doubleQuoteDict(dict):
    def __str__(self):
        return json.dumps(self)

class Aggregation(Resource):
    """
    Query Params:
        - field: required, specifing the column of the measurement where the aggregation should be performed
    """
    def get(self,id,action):
        user_id = request.headers.get("X-UserID")
        id = escape(id)
        query_params = request.args.to_dict()
        
        if "field" in query_params:
            field = escape(query_params["field"])
            del query_params["field"]
            result = get_instance_from_service(id)
            if result.status_code == 200:
                result = result.json() 
                server.server.app.logger.info("instance information from serving-service: " + json.dumps(result))
            else:
                return jsonify({"error": "user authorization could not be checked"})

            if user_id == result.get("UserId"):
                base_query = None
                if action == "sum":
                    base_query = 'SELECT SUM("' + field + '") FROM "' + id + '"'
                elif action == "mean":
                    base_query = 'SELECT MEAN("' + field + '") FROM "' + id + '"'
                elif action == "median":
                    base_query = 'SELECT MEDIAN("' + field + '") FROM "' + id + '"'
                elif action == "distinct":
                    base_query = 'SELECT DISTINCT("' + field + '") FROM "' + id + '"'
                elif action == "count":
                    base_query = 'SELECT COUNT("' + field + '") FROM "' + id + '"'
                elif action == "min":
                    base_query = 'SELECT MIN("' + field + '") FROM "' + id + '"'
                elif action == "max":
                    base_query = 'SELECT MAX("' + field + '") FROM "' + id + '"'

                if base_query:
                    """
                    interval = filter_params["interval"]
                    if interval:
                        # Use interval from query params to compute first possible date which will be used as condition to get only values from later dates
                        filter_params = {
                            "time.gte": datetime.datetime.now().replace(minute=datetime.datetime.now().minute - float(interval)).isoformat()
                        }
                        # Remove interval so that it dont get appended to the query 
                        del filter_params["interval"]
                    """ 

                    query, params = generate_query(base_query, id, user_id, query_params)
                    server.server.app.logger.info("Query: " + query)
                    server.server.app.logger.info("Params: " + str(params))
                    if params:
                        response = query_influx(query,user_id,params)
                        return jsonify(response.json())
                    else:
                        response = query_influx(query,user_id)
                        return jsonify(response.json())
                else:
                    return jsonify({"error": "aggregation method is not valid"})
            else:
                return jsonify({"error": "missing authorization for accessing measurement"})
        else:
            return jsonify({"error": "missing parameter field"})

class Measurements(Resource):
    def get(self):
        user_id = request.headers.get("X-UserID")
        query = "SHOW MEASUREMENTS"
        response = query_influx(query,user_id)
        return jsonify(response.json())

class Measurement(Resource):
    def get(self, id):
        user_id = request.headers.get("X-UserID")
        id = escape(id)
        result = get_instance_from_service(id)
        if result.status_code == 200:
            result = result.json() 
            server.server.app.logger.info("instance information from serving-service: " + json.dumps(result))
        else:
            return jsonify({"error": "user authorization could not be checked"})

        if user_id == result.get("UserId"):
            try:
                base_query = 'SELECT * FROM "' + id + '"'
                query_params = request.args
                query, params = generate_query(base_query,id, user_id,query_params)
            except ValueError as e:
                return jsonify({"error": "column does not exist"})

            server.server.app.logger.info("Query: " + query)
            server.server.app.logger.info("Params: " + str(params))

            if len(params) != 0:
                response = query_influx(query,user_id,params)
                # jsonfiy(response.json()) -> not just response, because in tests mockup is responding with support for json() but not casting to flask response object
                return jsonify(response.json())
            else:
                response = query_influx(query,user_id)
                return jsonify(response.json())
        else:
            return jsonify({"error": "missing authorization for accessing measurement"})

def query_influx(query,user_id,params=None):
    url = "http://{influx_db_host}:{influx_db_port}/query".format(influx_db_host=os.environ["INFLUX_DB_HOST"], influx_db_port=os.environ["INFLUX_DB_PORT"])
    if params:
        response = requests.post(url, params='db={db}&q={query}&params={params}'.format(db=user_id, query=query, params=str(params)))
        return response
    else: 
        response = requests.get(url, params="q={query}&db={db}".format(query=query,db=user_id))
        return response

def get_instance_from_service(instance_id):
    response = requests.get("http://{serving_service_host}:{serving_service_port}/instance/{id}".format(serving_service_host=os.environ["SERVING_SERVICE_HOST"], serving_service_port=os.environ["SERVING_SERVICE_PORT"], id=instance_id))
    return response        

def escape(value):
    """
    Escape a string, which can be user input. Therefore quotes have to be escaped and then wrapped into own quotes. 
    """
    escape_map = [('"','\\"'), ("'", "\\'")]
    for escape_pair in escape_map:
        value = value.replace(escape_pair[0], escape_pair[1])
    return value
    
def convert_to_int(value):
    """
    Try to convert the value to integer. If it raises an exception, it was probably a malicious string.
    """
    try:
        converted_integer = int(value)
        return converted_integer
    except ValueError as e:
        return False

def convert_to_float(value):
    """
    Try to convert the value to float. If it raises an exception, it was probably a malicious string.
    """
    try:
        converted_float = float(value)
        return converted_float
    except ValueError as e:
        return False
    
def check_field_value_type(field_name, measurement, user_id):
    if field_name == "time":
        return "string"
        
    query = 'SHOW FIELD KEYS FROM "{measurement}"'.format(measurement=escape(measurement))
    response = query_influx(query,user_id).json()
    fields = response["results"][0]["series"][0]["values"]
    for field in fields: 
        if field[0] == field_name:
            return field[1]
    return None   

def generate_query(base_query,id, user_id,query_params):
    """
    Generate query to get data from measurement in InfluxDB.
    """
    query = base_query
    bind_params = doubleQuoteDict()
    if len(query_params) != 0:
        for i,param in enumerate(query_params): 
            if param != "limit" and param != "offset":
                # Field names:
                # must be string WHERE "field" = ..
                # escape then put inside own double quotes 
                # Field values:
                # Problem: Type string or number not clear -> get measurement info whether should be number or string 
                # if string, escape, then bind
                # if not string, convert to float because firstly its treated as a string from the request.args
                field, action = param.split(".")
                escaped_field = escape(field)
                value = query_params[param]
                param_placeholder = "placeholder" + str(i) 
                checked_field_value = None 
                defined_field_value_type = check_field_value_type(field, id, user_id)
                if not defined_field_value_type:
                    raise ValueError
                
                if defined_field_value_type == "string":
                    checked_field_value = escape(value)
                elif defined_field_value_type == "int":
                    checked_field_value = convert_to_int(value)
                elif defined_field_value_type == "float":
                    checked_field_value = convert_to_float(value)

                if action == "gte":
                    action = ">="
                elif action == "lte":
                    action = "<="

                if "WHERE" not in query:
                    query += " WHERE"
                if query.split(" ")[-1] != "WHERE":
                    query += " AND"
                
                if checked_field_value and action and escaped_field:
                    bind_params[param_placeholder] = checked_field_value
                    query += " \"{field}\" {action} ${placeholder}".format(action=action,field=escaped_field,placeholder=param_placeholder)
        query += " ORDER BY time DESC"
        if "interval" in query_params:
            interval = query_params[param]
            query += " GROUP  BY time({interval})".format(interval=interval)
        
        if "limit" in query_params:
            converted_limit = convert_to_int(query_params[param])
            if converted_limit:
                query += " LIMIT {limit}".format(limit=converted_limit)
        
        if "offset" in query_params:
            converted_offset = convert_to_int(query_params[param])
            if converted_offset:
                query += " OFFSET {offset}".format(offset=converted_offset)
    return (query, bind_params)

