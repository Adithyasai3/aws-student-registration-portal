"""Student registration web app: stores registrations in DynamoDB and
announces each one through an SNS topic (email subscription).

Configuration comes from environment variables only; AWS credentials come
from the EC2 instance profile (LabInstanceProfile), never from this file.
"""
import logging
import os
import re
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError
from flask import Flask, render_template, request

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
ROLL_NO = os.environ.get("ROLL_NO", "")
TABLE_NAME = os.environ.get("TABLE_NAME", f"Students-{ROLL_NO}")
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN", "")

FIELDS = ["roll_no", "name", "course", "address", "email", "year"]
YEARS = ["1", "2", "3", "4", "5"]
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("student-app")

app = Flask(__name__)
table = boto3.resource("dynamodb", region_name=AWS_REGION).Table(TABLE_NAME)
sns = boto3.client("sns", region_name=AWS_REGION)


def validate(form):
    data = {f: (form.get(f) or "").strip() for f in FIELDS}
    errors = [f"{f.replace('_', ' ').title()} is required." for f in FIELDS if not data[f]]
    if data["email"] and not EMAIL_RE.match(data["email"]):
        errors.append("Email address is not valid.")
    if data["year"] and data["year"] not in YEARS:
        errors.append("Year of study must be between 1 and 5.")
    return data, errors


def notify(student, status):
    message = (
        "Student Registration Notification\n\n"
        f"University Roll Number: {student['roll_no']}\n"
        f"Student Name: {student['name']}\n"
        f"Course Name: {student['course']}\n"
        f"Registration Status: {status}\n"
    )
    resp = sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject=f"Registration {status} - {student['roll_no']}"[:100],
        Message=message,
    )
    return resp["MessageId"]


def render(status_code=200, **ctx):
    return render_template("index.html", roll_no=ROLL_NO, years=YEARS, **ctx), status_code


@app.get("/")
def index():
    return render()


@app.post("/register")
def register():
    data, errors = validate(request.form)
    if errors:
        return render(400, errors=errors, form=data)

    item = dict(data, registered_at=datetime.now(timezone.utc).isoformat())
    try:
        # Refuse to silently overwrite an existing registration.
        table.put_item(Item=item, ConditionExpression="attribute_not_exists(roll_no)")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return render(409, errors=[f"Roll number {data['roll_no']} is already registered."], form=data)
        log.exception("DynamoDB put_item failed")
        return render(500, errors=["Could not save the registration. Please try again."], form=data)
    log.info("Saved roll_no=%s to %s", data["roll_no"], TABLE_NAME)

    status = "SUCCESSFUL"
    try:
        message_id = notify(data, status)
        log.info("SNS publish ok roll_no=%s message_id=%s", data["roll_no"], message_id)
    except ClientError:
        log.exception("SNS publish failed")
        return render(200, student=data, status=status, message_id=None,
                      errors=["Registration saved, but the email notification could not be sent."])

    return render(200, student=data, status=status, message_id=message_id)


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
