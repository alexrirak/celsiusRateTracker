from flask import Flask, render_template
import requests
import json
import mysql.connector
from apscheduler.schedulers.background import BackgroundScheduler

from db import db_host, db_user, db_password, db_database

app = Flask(__name__)
sched = BackgroundScheduler(daemon=True)

CELSIUS_ENVIRONMENT = "staging"
CELSIUS_API_URL = "https://wallet-api.celsius.network/util/interest/rates" if CELSIUS_ENVIRONMENT == "prod" else "https://wallet-api.staging.celsius.network/util/interest/rates"
# queries defined at the very bottom
FETCH_COIN_DATA_QUERY = ""
INSERT_COIN_DATA_QUERY = ""
GET_LATEST_ROW_BY_COIN_QUERY = ""
GET_METADATA_BY_COIN_QUERY = ""
INSERT_COIN_METADATA_QUERY = ""
UPDATE_COIN_METADATA_QUERY = ""


@app.route('/')
def main():
    interestRates = get_celsius_rates()['interestRates']
    return render_template('main.html', interestRates=interestRates, env=CELSIUS_ENVIRONMENT)


# Fetches data from the db on all the coins
# returns data fro current rate and prior rate
@app.route('/fetchCoinData')
def fetch_coin_data():
    mydb = get_db_connection()

    mycursor = mydb.cursor()

    mycursor.execute(FETCH_COIN_DATA_QUERY)

    # this maps the column names onto the result set so that there is no guessing
    columns = mycursor.description
    result = [{columns[index][0]: column for index, column in enumerate(value)} for value in mycursor.fetchall()]

    mydb.close()

    return json.dumps(result, default=str)


# Given a coin and a rate checks if the rate is new and if so persists it to the DB
def insert_coin_rate(coin, rate):
    mydb = get_db_connection()

    mycursor = mydb.cursor()

    mycursor.execute(GET_LATEST_ROW_BY_COIN_QUERY.format(coin))

    existing_row = mycursor.fetchone()
    savedRate = float(existing_row[2])

    # Only save a new row if the rate has changed
    if savedRate != float(rate):
        mycursor.execute(INSERT_COIN_DATA_QUERY, (coin, rate))
        mydb.commit()

    mycursor.close()
    mydb.close()


# Given the name, symbol and image url of a coin, check if meta data exists in the DB
# if meta data doesnt exist insert it, if meta data has changed update it, otherwise do nothing
def update_coin_metadata(name, symbol, image_url):
    mydb = get_db_connection()

    # check if we have existing meta data for this coin
    mycursor = mydb.cursor()
    mycursor.execute(GET_METADATA_BY_COIN_QUERY.format(symbol))

    existing_row = mycursor.fetchone()

    # If we dont have meta data then insert it
    if existing_row is None:
        mycursor.execute(INSERT_COIN_METADATA_QUERY, (name, symbol, image_url))
        mydb.commit()
    # If we already have meta data check if it changed and if so update it
    else:
        if existing_row[1] != name or existing_row[2] != symbol or existing_row[3] != image_url:
            mycursor.execute(UPDATE_COIN_METADATA_QUERY.format(name, symbol, image_url, existing_row[0]))


# Refreshes coin data in our DB based on the celsius api
@app.route('/refreshCoinData')
@sched.scheduled_job('interval', id='refreshCoinData', hours=6)
def process_coin_rates():
    interestRates = get_celsius_rates()['interestRates']

    # for each coin, check if we need to update rate data and meta data
    for coin in interestRates:
        insert_coin_rate(coin["coin"], coin["rate"])
        update_coin_metadata(coin["currency"]["name"], coin["currency"]["short"], coin["currency"]["image_url"])

    # since this method is http accessible need to ensure we always return a http status code
    return ('Success', 200)


# Fetches the latest con rates from the celsius api
def get_celsius_rates():
    response = requests.get(CELSIUS_API_URL)

    if response.status_code == 200:
        return json.loads(response.text)

    return None


# reads a file in as a string
def get_string_from_file(file_path):
    file = open(file_path, 'r')
    result = file.read()
    file.close()
    return result


# returns a connection to the DB
def get_db_connection():
    return mysql.connector.connect(
        host=db_host,
        user=db_user,
        password=db_password,
        database=db_database
    )


if __name__ == '__main__':
    app.run()

# Define all our queries here cause python doesnt like me doing this on top
FETCH_COIN_DATA_QUERY = get_string_from_file('sql/fetchCoinData.sql')
INSERT_COIN_DATA_QUERY = get_string_from_file('sql/insertCoinData.sql')
GET_LATEST_ROW_BY_COIN_QUERY = get_string_from_file('sql/getLatestRowByCoin.sql')
GET_METADATA_BY_COIN_QUERY = get_string_from_file('sql/getMetadataByCoin.sql')
INSERT_COIN_METADATA_QUERY = get_string_from_file('sql/insertCoinMetadata.sql')
UPDATE_COIN_METADATA_QUERY = get_string_from_file('sql/updateCoinMetadata.sql')

# Start the scheduler
sched.start()


