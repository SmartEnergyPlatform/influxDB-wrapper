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

import os
from server import api, server
import unittest
from unittest import mock
import tempfile
import flask
import json

os.environ["INFLUX_DB_HOST"] = ""
os.environ["INFLUX_DB_PORT"] = ""
os.environ["SERVING_SERVICE_HOST"] = ""
os.environ["SERVING_SERVICE_PORT"] = ""

def mocked_requests_query_influx(query, user_id, params=None):
    class MockResponse:
        def __init__(self, json_data, status_code):
            self.json_data = json_data
            self.status_code = status_code

        def json(self):
            return self.json_data

    if query == 'SHOW FIELD KEYS FROM "instance"':
        return MockResponse({ 
                "results": [
                    {
                        "series": [
                            {
                                "values": [
                                    ["string_value", "string"],["int_value", "int"],["float_value", "float"]
                                ]
                            }
                        ]
                    }
                ]
        }, 200)
    elif query == "SHOW MEASUREMENTS":
        return MockResponse({ 
            "results": [
                {
                    "series": [
                        {
                            "values": [
                                ["test", "test"]
                            ]
                        }
                    ]
                }
            ]
        }, 200)
    else:
        return MockResponse(20, 200)


def mocked_requests_get_instances(id):
    class MockResponse:
        def __init__(self, json_data, status_code):
            self.json_data = json_data
            self.status_code = status_code

        def json(self):
            return self.json_data

    if id == 'instance':
        return MockResponse({"UserId": "user"}, 200)
    elif id == 'instance2':
        return MockResponse({"UserId": "user2"}, 200)

    return MockResponse(None, 404)

class QueryTestCase(unittest.TestCase):
    def test_convert_float(self):
        result = api.convert_to_float(2)
        self.assertTrue(2.0 == result)
        result = api.convert_to_float(2.0)
        self.assertTrue(2.0 == result)
        result = api.convert_to_float("2")
        self.assertTrue(2.0 == result)
        result = api.convert_to_float("2.0")
        self.assertTrue(2.0 == result)
        result = api.convert_to_float("a")
        self.assertFalse(result)

    def test_convert_int(self):
        result = api.convert_to_int(2)
        self.assertTrue(2 == result)
        result = api.convert_to_int(2.0)
        self.assertTrue(2 == result)
        result = api.convert_to_int("2")
        self.assertTrue(2 == result)
        result = api.convert_to_int("2.0")
        self.assertFalse(result)
        result = api.convert_to_int("a")
        self.assertFalse(result)

    def test_escape(self):
        result = api.escape('"measurement"')
        self.assertTrue(result == '\\"measurement\\"')
        result = api.escape('" DROP "')
        self.assertTrue(result == '\\" DROP \\"')
        result = api.escape("'DROP'")
        self.assertTrue(result == "\\'DROP\\'")
        # SQL Injection SELECT * FROM 'test' WHERE a = 'input' -> input = '; DROP ' -> SELECT * FROM 'test' WHERE a = ''; DROP ''
        result = api.escape("'; DROP '")
        print(result)
        self.assertTrue(result == "\\'; DROP \\'") # \\ not \ because single one only marks escaping but should be part of the string

    @mock.patch('server.api.query_influx', side_effect=mocked_requests_query_influx)
    def test_check_value_type(self,mock):
        result = api.check_field_value_type("string_value", "instance", "user")
        self.assertTrue(result == "string")
        result = api.check_field_value_type("int_value", "instance", "user")
        self.assertTrue(result == "int")
        result = api.check_field_value_type("float_value", "instance", "user")
        self.assertTrue(result == "float")
    
    @mock.patch('server.api.query_influx', side_effect=mocked_requests_query_influx)
    def test_query_generation(self,mock):
        with server.app.test_request_context('/path?limit=1&offset=2&int_value.gte=20&string_value.lte=""; DROP""'):
            self.assertTrue(flask.request.args['limit'] == "1")
            self.assertTrue(flask.request.args['offset'] == "2")
            self.assertTrue(flask.request.args['int_value.gte'] == "20")
            user_id = "user"
            query,bind_params = api.generate_query('SELECT * FROM "instance"', 'instance', user_id, flask.request.args)
            self.assertTrue(query == 'SELECT * FROM "instance" WHERE "int_value" >= $placeholder2 AND "string_value" <= $placeholder3')
            self.assertTrue(bind_params == {"placeholder2": 20, "placeholder3": '\\"\\"; DROP\\"\\"'})

        with server.app.test_request_context('/path?value.lte=1'):
            # TODO test with uery param that not exists -> correct error message
            user_id = "user"
            with self.assertRaises(ValueError) as cm:
                query,bind_params = api.generate_query('SELECT * FROM "instance"', "instance", user_id, flask.request.args)
        
        with server.app.test_request_context('/path?int_value.gte=20'):
            self.assertTrue(flask.request.args['int_value.gte'] == "20")
            user_id = "user"
            query,bind_params = api.generate_query('SELECT * FROM "instance"', 'instance', user_id, flask.request.args)
            self.assertTrue(query == 'SELECT * FROM "instance" WHERE "int_value" >= $placeholder0')
            self.assertTrue(bind_params == {"placeholder0": 20})

        with server.app.test_request_context('/path?&offset=2&int_value.gte=20'):
            self.assertTrue(flask.request.args['int_value.gte'] == "20")
            user_id = "user"
            query,bind_params = api.generate_query('SELECT * FROM "instance"', 'instance', user_id, flask.request.args)
            self.assertTrue(query == 'SELECT * FROM "instance" WHERE "int_value" >= $placeholder1 OFFSET 20')
            self.assertTrue(bind_params == {"placeholder1": 20})

        with server.app.test_request_context('/path?limit=20'):
            self.assertTrue(flask.request.args['limit'] == "20")
            user_id = "user"
            query,bind_params = api.generate_query('SELECT * FROM "instance"', "instance", user_id, flask.request.args)
            self.assertTrue(query == 'SELECT * FROM "instance" LIMIT 20')
            self.assertTrue(bind_params == {})

class ApiTestCase(unittest.TestCase):
    def setUp(self):
        self.app = server.app.test_client()

    @mock.patch('server.api.query_influx', side_effect=mocked_requests_query_influx)
    def test_measurements_endpoint(self,mock):
        user_id = "user"
        response = self.app.get("/measurements", headers={'X-UserID': user_id})
        self.assertTrue(response)

    @mock.patch('server.api.get_instance_from_service', side_effect=mocked_requests_get_instances)
    @mock.patch('server.api.query_influx', side_effect=mocked_requests_query_influx)
    def test_measurement_endpoint(self,mock,mock2):
        user_id = "user"
        instance_id = "instance"
        response = self.app.get("/measurement/" + instance_id, headers={'X-UserID': user_id})
        self.assertIsNotNone(response.data)
        # tests should not handle data only check if data is coming ??
    
        user_id = "user2"
        instance_id = "instance"
        response = self.app.get("/measurement/" + instance_id, headers={'X-UserID': user_id})
        self.assertTrue(json.loads(response.data) == {"error": "missing authorization for accessing measurement"})

        user_id = "user"
        instance_id = "instance"
        response = self.app.get("/measurement/" + instance_id, headers={'X-UserID': user_id}, query_string={"string_value.lte": "test"})
        self.assertIsNotNone(response.data)

        user_id = "user"
        instance_id = "instance"
        response = self.app.get("/measurement/" + instance_id, headers={'X-UserID': user_id}, query_string={"value.lte": "test"})
        self.assertTrue(json.loads(response.data) == {"error": "column does not exist"})

if __name__ == '__main__':
    unittest.main()