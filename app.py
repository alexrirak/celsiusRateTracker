import sys

from flask import Flask, render_template, request, abort
import requests
import json
import mysql.connector
from apscheduler.schedulers.background import BackgroundScheduler
import smtplib
import ssl
import datetime
import uuid
import os
import binascii
import urllib.parse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

app = Flask(__name__)
sched = BackgroundScheduler(daemon=True)

ENVIRONMENT = os.getenv("ENVIRONMENT", "staging")
CELSIUS_API_URL = "https://wallet-api.celsius.network/util/interest/rates" if ENVIRONMENT.upper() == "PROD" else "https://wallet-api.staging.celsius.network/util/interest/rates"
DATABASE_HOST = os.getenv("DATABASE_HOST")
DATABASE_USER = os.getenv("DATABASE_USER")
DATABASE_PASS = os.getenv("DATABASE_PASS")
DATABASE_SCHM = os.getenv("DATABASE_SCHM")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_SERVER = os.getenv("EMAIL_SERVER")
BASE_HOST = os.getenv("BASE_HOST", "https://celsiustracker.com")
# queries defined at the very bottom
FETCH_COIN_DATA_QUERY = ""
INSERT_COIN_DATA_QUERY = ""
GET_LATEST_ROW_BY_COIN_QUERY = ""
GET_METADATA_BY_COIN_QUERY = ""
INSERT_COIN_METADATA_QUERY = ""
UPDATE_COIN_METADATA_QUERY = ""
GET_SUBSCRIBED_EMAILS = ""
GET_ALL_SUBSCRIBED_EMAILS = ""
GET_COIN_LIST = ""
INSERT_EMAIL_ALERT = ""
CHECK_EMAIL_CONFIRMED = ""
GET_SUBSCRIBED_COINS = ""
GET_SUBSCRIPTION_STRING_BY_EMAIL = ""


# Renders the main view
@app.route('/')
def main():
    return render_template('main.html', env=ENVIRONMENT, coinList=get_coin_list(), BASE_HOST=BASE_HOST)


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

    mycursor.close()
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

    mycursor.close()
    mydb.close()


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


# Given an email and list of coins subscribes for alerts
@app.route('/registerEmail', methods=['POST'])
def register_email():
    if not request.json or not 'email' in request.json or not 'coins' in request.json:
        abort(400)
    else:
        # Checks if this email has already been confirmed
        emailConfirmed = is_email_confirmed(request.json["email"])
        confirmId = str(uuid.uuid4())
        existing_coin_subscriptions = get_subscriptions(request.json["email"])
        insert_data = []
        for coin in request.json["coins"]:
            # Dont duplicate if subscription already exists
            if coin in existing_coin_subscriptions:
                continue
            insert_data.append((coin, request.json["email"], emailConfirmed, confirmId if not emailConfirmed else None))

        with get_db_connection() as db:
            with db.cursor() as cursor:
                # The MYSQL executor optimizes our insert into a single query when using executemany
                cursor.executemany(INSERT_EMAIL_ALERT, insert_data)
                db.commit()

        if(not emailConfirmed):
            send_email_confirmation_request(request.json["email"], confirmId)

    return ('Success', 201)


# Marks an email as confirmed in the database so that it starts receiving alerts
@app.route('/confirmEmail/<string:confirmation_id>')
def confirm_email(confirmation_id: str):
    mydb = get_db_connection()

    mycursor = mydb.cursor()

    # this should make no difference if its the id we expect but it will hopefully prevent malicious input
    confirmation_id = urllib.parse.quote_plus(confirmation_id)

    result_args = mycursor.callproc('sp_ConfirmEmail',[confirmation_id, 0])
    mydb.commit()

    mycursor.close()
    mydb.close()

    return render_template('confirmed.html',
                           env=ENVIRONMENT,
                           success=True if int(result_args[1]) == 1 else False,
                           BASE_HOST=BASE_HOST)


# Displays the unsubscribe landing page
# For users not coming from an email it encodes he email
@app.route('/unsubscribe/')
def unsubscribe_landing_page():
    return render_template('unsubscribeLanding.html',
                           env=ENVIRONMENT,
                           BASE_HOST=BASE_HOST)


# Displays the unsubscribe page given an email id string
# email id is just the person's email in hex encoded form
@app.route('/unsubscribe/<string:email_id>')
def unsubscribe_email_page(email_id: str):
    email = binascii.unhexlify(email_id.encode()).decode()

    mydb = get_db_connection()

    mycursor = mydb.cursor()

    mycursor.execute(GET_SUBSCRIBED_COINS % email)

    # this maps the column names onto the result set so that there is no guessing
    columns = mycursor.description
    subscribed_coins = [{columns[index][0]: column for index, column in enumerate(value)} for value in mycursor.fetchall()]

    mycursor.close()
    mydb.close()

    return render_template('unsubscribe.html',
                           env=ENVIRONMENT,
                           email=email,
                           email_id=email_id,
                           BASE_HOST=BASE_HOST,
                           subscribed_coins=subscribed_coins,
                           sub_error=True if len(subscribed_coins) == 0 else False)


# Calls a store proc to unsubscribe (delete) given email from the DB
@app.route('/unsubscribe/<string:email_id>', methods=['DELETE'])
def unsubscribe_email(email_id: str):
    email = binascii.unhexlify(email_id.encode()).decode()

    mydb = get_db_connection()

    mycursor = mydb.cursor()

    mycursor.callproc('sp_Unsubscribe', [email])
    mydb.commit()

    mycursor.close()
    mydb.close()

    return ('Success', 200)


# Displays the disclaimer
@app.route('/disclaimer')
def disclaimer_page():
    return render_template('disclaimer.html',
                           env=ENVIRONMENT,
                           BASE_HOST=BASE_HOST)


# Displays the support us page
@app.route('/supportUs')
def support_us_page():
    return render_template('supportUs.html',
                           env=ENVIRONMENT,
                           BASE_HOST=BASE_HOST)


# Checks whether a subscription exists for the given email
# if it does then returns the email id
@app.route('/unsubscribeCheck/<string:email>')
def check_unsubscribe_email(email: str):
    if is_email_confirmed(email):
        email_id = binascii.hexlify(email.encode()).decode()
        return ({"emailId":email_id}, 200)
    else:
        return ('NotFound', 404)


@app.route('/migrationNotification/<string:confirm>')
def send_migration_notification(confirm: str):
    if confirm != "YES":
        return ('ERROR', 500)

    # Sends an email using the rate change template to the given email
    emails = get_all_subscribed_emails()
    body = render_template('emailMigrationNotice.html', BASE_HOST=BASE_HOST)
    for email in emails:
        print("Sending to ", email.get('email'))
        send_email(email.get('email'), "[Celsius Tracker] We are Moving - Final Notice", body)

    return (str(len(emails)), 200)


# Gets the list of subscriber emails given a list of coins which changed
def get_all_subscribed_emails():
    mydb = get_db_connection()

    mycursor = mydb.cursor()

    # format the list as string but strip the brackets
    mycursor.execute(GET_ALL_SUBSCRIBED_EMAILS)

    # this maps the column names onto the result set so that there is no guessing
    columns = mycursor.description
    result = [{columns[index][0]: column for index, column in enumerate(value)} for value in mycursor.fetchall()]

    mycursor.close()
    mydb.close()

    return result

# Checks if this email has already been confirmed
def is_email_confirmed(email: str):
    with get_db_connection() as db:
        with db.cursor() as cursor:
            cursor.execute(CHECK_EMAIL_CONFIRMED % email)

            existing_row = cursor.fetchone()

            if existing_row[0] is not None and int(existing_row[0]) == 1:
                return True
            return False


# Returns a list of subscriptions given an email
def get_subscriptions(email: str):

    with get_db_connection() as db:
        with db.cursor() as cursor:
            cursor.execute(GET_SUBSCRIPTION_STRING_BY_EMAIL % (email))
            result = cursor.fetchone()

            if result is not None:
                return result[0].split(",")

            return []


# Send out email alerts for the changed rates
def send_out_email_alerts(changed_rates):
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


# Gets the list of subscriber emails given a list of coins which changed
def get_subscribed_emails(changed_rates):
    mydb = get_db_connection()

    mycursor = mydb.cursor()

    # format the list as string but strip the brackets
    mycursor.execute(GET_SUBSCRIBED_EMAILS.format(str(changed_rates).strip("[]")))

    # this maps the column names onto the result set so that there is no guessing
    columns = mycursor.description
    result = [{columns[index][0]: column for index, column in enumerate(value)} for value in mycursor.fetchall()]

    mycursor.close()
    mydb.close()

    return result


# Based on a list of coins, fetches the relevant change data from the api
def get_coin_change_data(changed_rates):
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


# Converts APR to APY with ((1+(B4/52))^(52))-1
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
        host=DATABASE_HOST,
        user=DATABASE_USER,
        password=DATABASE_PASS,
        database=DATABASE_SCHM
    )


# Returns the list of coins in the DB
def get_coin_list():
    mydb = get_db_connection()

    mycursor = mydb.cursor()

    mycursor.execute(GET_COIN_LIST)

    # this maps the column names onto the result set so that there is no guessing
    columns = mycursor.description
    result = [{columns[index][0]: column for index, column in enumerate(value)} for value in mycursor.fetchall()]

    mycursor.close()
    mydb.close()

    return result


# sends an email to the specified email with the given subject and body
def send_email(to_email: str, subject: str, body: str):

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = "Celsius Tracker {}<{}>".format("" if ENVIRONMENT.upper() == "PROD" else ENVIRONMENT.upper(),
                                                      EMAIL_USER)
    message["To"] = to_email

    message.attach(MIMEText(body, "html"))

    # Create secure connection with server and send email
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(EMAIL_SERVER, 465, context=context) as server:
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(
            EMAIL_USER, to_email, message.as_string()
        )


# Sends an email using the email confirmation template to the given email
def send_email_confirmation_request(to_email: str, confirm_id: str):
    body = render_template('emailConfirmation.html', confirmId=confirm_id, BASE_HOST=BASE_HOST)
    send_email(to_email, "[Celsius Tracker] Please confirm your email address", body)


# Sends an email using the rate change template to the given email
def send_rate_change_notification(to_email: str, coinData):
    email_id = binascii.hexlify(to_email.encode()).decode()
    body = render_template('emailAlert.html', coinData=coinData, BASE_HOST=BASE_HOST, EMAIL_ID=email_id)
    send_email(to_email, "[Celsius Tracker] Celsius Rate Change", body)


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
GET_ALL_SUBSCRIBED_EMAILS = get_string_from_file('sql/getAllSubscribedEmails.sql')
GET_COIN_LIST = get_string_from_file('sql/getCoinList.sql')
INSERT_EMAIL_ALERT = get_string_from_file('sql/insertEmailAlert.sql')
CHECK_EMAIL_CONFIRMED = get_string_from_file('sql/checkIfEmailConfirmed.sql')
GET_SUBSCRIBED_COINS = get_string_from_file('sql/getSubscribedCoins.sql')
GET_SUBSCRIPTION_STRING_BY_EMAIL = get_string_from_file('sql/getSubscriptionsStringByEmail.sql')

# Start the scheduler
sched.start()

# Load env vars
load_dotenv()
if DATABASE_HOST is None or \
        DATABASE_USER is None or \
        DATABASE_PASS is None or \
        DATABASE_SCHM is None or \
        EMAIL_USER is None or \
        EMAIL_PASS is None or \
        EMAIL_SERVER is None:
    print("*** Missing environment variables ***")
    sys.exit()

