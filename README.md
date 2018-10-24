# How does it work 
- see swagger file
- the real database for the influx DB API request is the user id which gets set in this service

# Build and run
## Python
### Requirements
```shell
pip3 install -r requirements.txt
```
### Run 
```
INFLUX_DB_HOST=host INFLUX_DB_PORT=port SERVING_SERVICE_HOST=host SERVING_SERVICE_PORT=port FLASK_APP=./server/server.py flask run --host=0.0.0.0
```

## Docker
### Build
```
docker build -t influx-auth .
```

### Run
```
docker run -p 5000:5000 -e "INFLUX_DB_HOST=host" -e "INFLUX_DB_PORT=port" -e "SERVING_SERVICE_HOST=host" -e "SERVING_SERVICE_PORT=port" influx-auth
```
```
docker-compose up
```

# Usage
see swagger file for api specification 

# Environment Variables
- INFLUX_DB_HOST
- INFLUX_DB_PORT
- SERVING_SERVICE_HOST
- SERVING_SERVICE_PORT

# SQL Injection
- PROBLEM SQL Injection: field names should be set dynamically because they are set in the device type
- parameter binding / prepared statements not wokring with column names -> escaping double quotes -> 'WHERE "{escaped}"'.format(escaped=escaped_string)
- LIMIT AND OFFSET are numbers -> converting to float will fail if its a string 
- Field values in WHERE are safe by parameter binding from InfluxDB
- SELECT FROM id is safe because if its measurements id like 123; DROP the check_authorization function will return false 
- Field names will be added like influx bind_param, check if it should be stirng
 Field values double check:  check if it should be stirng, then escape else if number make type check

# Tests
```
python3 -m unittest discover
```