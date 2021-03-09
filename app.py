from flask import Flask, render_template
import requests
import json
import mysql.connector
from apscheduler.schedulers.background import BackgroundScheduler
import smtplib
import ssl
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from db import db_host, db_user, db_password, db_database, email_username, email_smtp_server, email_password

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
    return render_template('main.html', env=CELSIUS_ENVIRONMENT)


# Fetches data from the db on all the coins
# returns data for current rate and prior rate
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
# Returns true if it inserts a row, false if the rate was the same
def insert_coin_rate(coin: str, rate):
    mydb = get_db_connection()

    mycursor = mydb.cursor()

    rate_updated = False

    mycursor.execute(GET_LATEST_ROW_BY_COIN_QUERY.format(coin))

    existing_row = mycursor.fetchone()

    # Check if the row exists
    if existing_row is not None:
        savedRate = float(existing_row[2])

        # Only save a new row if the rate has changed
        if savedRate != float(rate):
            mycursor.execute(INSERT_COIN_DATA_QUERY, (coin, rate))
            mydb.commit()
            rate_updated = True
    else:
        mycursor.execute(INSERT_COIN_DATA_QUERY, (coin, rate))
        mydb.commit()
        rate_updated = True

    mycursor.close()
    mydb.close()
    return rate_updated


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
    changed_rates = []

    # for each coin, check if we need to update rate data and meta data
    for coin in interestRates:
        coin_rate_changed = insert_coin_rate(coin["coin"], coin["rate"])
        update_coin_metadata(coin["currency"]["name"], coin["currency"]["short"], coin["currency"]["image_url"])
        if coin_rate_changed:
            changed_rates.append(coin["coin"])

    # If there are rates which changed trigger an async email alert
    if len(changed_rates) > 0:
        # sched.add_job(send_out_email_alerts, None, [changed_rates])
        send_out_email_alerts(changed_rates)

    # since this method is http accessible need to ensure we always return a http status code
    return ('Success', 200)


# TODO: remove this method
@app.route('/triggerEmail')
def trigger_email():
    send_out_email_alerts(["BTC"])
    return ('Success', 200)


# Send out email alerts for the changed rates
def send_out_email_alerts(changed_rates: list[str]):
    coin_data = get_coin_change_data(changed_rates)
    subscribers = get_subscribed_emails(changed_rates)

    if len(subscribers) < 1:
        return

    for sub in subscribers:
        subed_coins = sub["coins"].split(",")
        coinData = {}
        for coin in subed_coins:
            coinData[coin] = coin_data.get(coin)


        send_rate_change_notification(sub["email"], coinData)


def get_subscribed_emails(changed_rates: list[str]):
    mydb = get_db_connection()

    mycursor = mydb.cursor()

    # format the list as string but strip the brackets
    mycursor.execute(GET_SUBSCRIBED_EMAILS.format(str(changed_rates).strip("[]")))

    # this maps the column names onto the result set so that there is no guessing
    columns = mycursor.description
    result = [{columns[index][0]: column for index, column in enumerate(value)} for value in mycursor.fetchall()]

    mydb.close()

    return result


# Based on a list of coins, fetches the relevant change data from the api
def get_coin_change_data(changed_rates: list[str]):
    coin_data = json.loads(fetch_coin_data())
    coin_change_data = {}

    for coin_record in coin_data:
        if coin_record["coin"] in changed_rates:
            coin_record["latest_rate"] = apr_to_apy(float(coin_record["latest_rate"]))
            coin_record["prior_rate"] = apr_to_apy(float(coin_record["prior_rate"]))
            coin_record["rate_diff"] = coin_record["latest_rate"] - coin_record["prior_rate"]
            coin_record["latest_date"] = datetime.datetime.strptime(coin_record["latest_date"], '%Y-%m-%d %H:%M:%S').date()
            coin_change_data[coin_record["coin"]] = coin_record

    return coin_change_data


# Fetches the latest coin rates from the celsius api
def get_celsius_rates():
    response = requests.get(CELSIUS_API_URL)

    if response.status_code == 200:
        return json.loads(response.text)

    return None


def apr_to_apy(apr: float) -> float:
    apr = float(apr)
    return ((1 + (apr / 52)) ** 52) - 1


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


# sends an email to the specified email with the given subject and body
def send_email(to_email: str, subject: str, body: str):

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = email_username
    message["To"] = to_email

    message.attach(MIMEText(body, "html"))

    # Create secure connection with server and send email
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(email_smtp_server, 465, context=context) as server:
        server.login(email_username, email_password)
        server.sendmail(
            email_username, to_email, message.as_string()
        )


# Sends an email using the rate change template to the given email
def send_rate_change_notification(to_email: str, coinData):
    body = render_template('email.html', coinData=coinData)
    send_email(to_email, "Celsius Rate Change", body)


if __name__ == '__main__':
    app.run()

# Define all our queries here cause python doesnt like me doing this on top
FETCH_COIN_DATA_QUERY = get_string_from_file('sql/fetchCoinData.sql')
INSERT_COIN_DATA_QUERY = get_string_from_file('sql/insertCoinData.sql')
GET_LATEST_ROW_BY_COIN_QUERY = get_string_from_file('sql/getLatestRowByCoin.sql')
GET_METADATA_BY_COIN_QUERY = get_string_from_file('sql/getMetadataByCoin.sql')
INSERT_COIN_METADATA_QUERY = get_string_from_file('sql/insertCoinMetadata.sql')
UPDATE_COIN_METADATA_QUERY = get_string_from_file('sql/updateCoinMetadata.sql')
GET_SUBSCRIBED_EMAILS = get_string_from_file('sql/getSubscribedEmails.sql')

# Start the scheduler
sched.start()


