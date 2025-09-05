from flask import Flask, request, jsonify, render_template, g
import sqlite3
import os
import time
import paho.mqtt.client as mqtt
import ssl
import json
import threading
import boto3
import math
import sys
import motor_alert

# --- Flask App Setup ---
app = Flask(__name__)

# --- Database Paths ---
base_folder = os.path.dirname(os.path.abspath(__file__))
TEMP_DB = os.path.join(base_folder, "temperature_data.db")
VIB_DB = os.path.join(base_folder, "vibration_data.db")

# --- AWS IoT MQTT Setup ---
#AWS_ENDPOINT = "awq9r6zn9ccrm-ats.iot.us-east-1.amazonaws.com"
#CERT_PATH = "/var/www/html/"
#CA_CERT = os.path.join(CERT_PATH, "RootCA1.pem")
#CERT_FILE = os.path.join(CERT_PATH, "certificate.pem.crt")
#EY_FILE = os.path.join(CERT_PATH, "private.pem.key")

AWS_ENDPOINT = "awq9r6zn9ccrm-ats.iot.us-east-1.amazonaws.com"
CERT_PATH = "/Users/kakaell/Desktop/Sandhy Document/ICC Intership/Programming/Machine_Health_Analysis_-IoT-/"
CA_CERT = os.path.join(CERT_PATH, "RootCA1.pem")
CERT_FILE = os.path.join(CERT_PATH, "certificate.pem.crt")
KEY_FILE = os.path.join(CERT_PATH, "private.pem.key")

client = mqtt.Client()
def on_connect(client, userdata, flags, rc):
    print("Connected to AWS IoT with result code", rc)

client.on_connect = on_connect
client.tls_set(ca_certs=CA_CERT, certfile=CERT_FILE, keyfile=KEY_FILE, tls_version=ssl.PROTOCOL_TLS)
client.tls_insecure_set(True)
client.connect(AWS_ENDPOINT, 8883, 60)
client.loop_start()

# --- SQLite DB Connections ---
def get_temp_db():
    db = getattr(g, '_temp_db', None)
    if db is None:
        db = g._temp_db = sqlite3.connect(TEMP_DB)
        db.execute("""
            CREATE TABLE IF NOT EXISTS temperatures (
                id INTEGER PRIMARY KEY,
                temperature REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
    return db

def get_vib_db():
    db = getattr(g, '_vib_db', None)
    if db is None:
        db = g._vib_db = sqlite3.connect(VIB_DB)
        db.execute("""
            CREATE TABLE IF NOT EXISTS vibrations (
                id INTEGER PRIMARY KEY,
                vibration REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
    return db

@app.teardown_appcontext
def close_connections(exception):
    temp_db = getattr(g, '_temp_db', None)
    vib_db = getattr(g, '_vib_db', None)
    if temp_db is not None:
        temp_db.close()
    if vib_db is not None:
        vib_db.close()

# --- Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/data', methods=['POST'])
def receive_data():
    temp_db = get_temp_db()
    vib_db = get_vib_db()

    data = request.get_json()
    if data and "temperature" in data:
        temperature = data["temperature"]
        vibration = data.get("vibration", None)

        print(f"Temperature: {temperature}°C, Vibration: {vibration}")

        temp_db.execute("INSERT INTO temperatures (temperature) VALUES (?)", (temperature,))
        temp_db.commit()

        if vibration is not None:
            vib_db.execute("INSERT INTO vibrations (vibration) VALUES (?)", (vibration,))
            vib_db.commit()

        return jsonify({"status": "success", "message": "Data received!"}), 200
    else:
        return jsonify({"status": "error", "message": "No data received"}), 400

@app.route('/live-data')
def live_data():
    conn_temp = sqlite3.connect(TEMP_DB)
    conn_vib = sqlite3.connect(VIB_DB)

    temp_cursor = conn_temp.cursor()
    vib_cursor = conn_vib.cursor()

    temp_cursor.execute("SELECT timestamp, temperature FROM temperatures ORDER BY timestamp DESC")
    vib_cursor.execute("SELECT timestamp, vibration FROM vibrations ORDER BY timestamp DESC")

    temp_rows = temp_cursor.fetchall()
    vib_rows = vib_cursor.fetchall()

    conn_temp.close()
    conn_vib.close()

    temp_rows = temp_rows[::-1]
    vib_rows = vib_rows[::-1]

    return jsonify({
        'temp_timestamps': [row[0] for row in temp_rows],
        'temperature': [row[1] for row in temp_rows],
        'vib_timestamps': [row[0] for row in vib_rows],
        'vibration': [row[1] for row in vib_rows]
    })

@app.route('/latest')
def latest_readings():
    conn_temp = sqlite3.connect(TEMP_DB)
    conn_vib = sqlite3.connect(VIB_DB)

    temp_cursor = conn_temp.cursor()
    vib_cursor = conn_vib.cursor()

    temp_cursor.execute("SELECT temperature FROM temperatures ORDER BY id DESC LIMIT 1")
    vib_cursor.execute("SELECT vibration FROM vibrations ORDER BY id DESC LIMIT 1")

    temp = temp_cursor.fetchone()
    vib = vib_cursor.fetchone()

    conn_temp.close()
    conn_vib.close()

    return jsonify({
        'temperature': temp[0] if temp else 0,
        'vibration': vib[0] if vib else 0
    })
# --- Background Publisher to AWS ---
def publish_to_aws():
    timestream = boto3.client('timestream-write', region_name='us-east-1')

    # Add counters
    high_temp_count = 0
    low_vibra_count = 0

    while True:
        try:
            conn_temp = sqlite3.connect(TEMP_DB)
            conn_vib = sqlite3.connect(VIB_DB)

            temp_cursor = conn_temp.cursor()
            vib_cursor = conn_vib.cursor()

            temp_cursor.execute("SELECT temperature FROM temperatures ORDER BY id DESC LIMIT 1")
            vib_cursor.execute("SELECT vibration FROM vibrations ORDER BY id DESC LIMIT 1")

            temp = temp_cursor.fetchone()
            vib = vib_cursor.fetchone()

            conn_temp.close()
            conn_vib.close()

            temperature = float(temp[0]) if temp else 0.0
            vibration = float(vib[0]) if vib else 0.0

            # Notification counting logic
            if temperature > 25:
                high_temp_count += 1
                print(f"High Temperature detected: {temperature}°C (Count: {high_temp_count})")
            else:
                print(f"Normal Temperature: {temperature}°C")

            if vibration < 1:
                low_vibra_count += 1
                print(f"Low Vibration detected: {vibration}Hz (Count: {low_vibra_count})")
            else:
                print(f"Normal Vibration: {vibration}Hz")

            # Check if thresholds exceeded
            if high_temp_count > 10 and low_vibra_count > 10:
                print("MOTOR FAN WARNING: Possible Future Failure Detected!")

                # Send SMS + Email Alerts
                phone_number = '+61481388436'
                message = 'MOTOR FAN WARNING: Possible Future Failure!'
                api_key = 'c716229907f52813f9e0d60de08e7314050bcb8fqbiGX4RRmIuMWD56C1Q8AtsjJ'

                to_email = "daud.soumilena23@gmail.com"
                email_address = "sandhywaer21@gmail.com"
                email_password = "ctommjogyxugcfwi"

                # Call the functions to send alerts
                email_response = motor_alert.email_motor_alert(to_email, email_address, email_password)
                text_response = motor_alert.text_motor_alert(phone_number, message, api_key)

                # Reset counters after alert sent
                high_temp_count = 0
                low_vibra_count = 0

            if not (math.isfinite(temperature) and math.isfinite(vibration)):
                print("⚠️ Skipping invalid data...")
                time.sleep(5)
                continue

            current_time = str(int(time.time() * 1000))

            msg = {
                'time': current_time,
                'temperature': temperature,
                'vibration': vibration,
                'measure_value_type': 'DOUBLE',
                'dimensions': [
                    {'name': 'device', 'value': 'raspberry-pi'}
                ]
            }

            # Publish to MQTT
            client.publish("raspi/data", payload=json.dumps(msg), qos=0, retain=False)

            # Write to Timestream
            timestream.write_records(
                DatabaseName='IoTsensorDB',
                TableName='TemperatureTable',
                Records=[{
                    'Dimensions': [{'Name': 'device', 'Value': 'raspberry-pi'}],
                    'MeasureName': 'temperature',
                    'MeasureValue': str(temperature),
                    'MeasureValueType': 'DOUBLE',
                    'Time': current_time
                }]
            )

            timestream.write_records(
                DatabaseName='IoTsensorDB',
                TableName='VibrationTable',
                Records=[{
                    'Dimensions': [{'Name': 'device', 'Value': 'raspberry-pi'}],
                    'MeasureName': 'vibration',
                    'MeasureValue': str(vibration),
                    'MeasureValueType': 'DOUBLE',
                    'Time': current_time
                }]
            )

            print("✅ Data published to AWS.")

        except Exception as e:
            print("❌ Publish error:", e)

        time.sleep(5)


# --- Start Background Publisher ---
threading.Thread(target=publish_to_aws, daemon=True).start()

# --- Run Flask App ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050, debug=True)
