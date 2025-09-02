import smtplib
from email.mime.text import MIMEText
import requests

def email_motor_alert(to_email, email_address, email_password):
    subject = "Motor Fan Future Failure Warning"
    body = "Warning: The motor fan is predicted to break due to high temperature and unstable vibration readings detected more than 10 times."

    message = MIMEText(body)
    message['Subject'] = subject
    message['From'] = email_address
    message['To'] = to_email

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(email_address, email_password)
            server.sendmail(email_address, to_email, message.as_string())
        print("Motor alert email sent successfully.")
    except Exception as e:
        print("Failed to send motor alert email:", e)

def text_motor_alert(phone_number, message, api_key):
    try:
        response = requests.post('https://textbelt.com/text', {
            'phone': phone_number,
            'message': message,
            'key': api_key,
        })
        print(response.json())
    except Exception as e:
        print("Failed to send motor alert SMS:", e)
