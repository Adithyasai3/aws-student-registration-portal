# Student Registration (DynamoDB + SNS)

Flask web app that collects a student's roll number, name, course, address,
email and year of study, writes the record to DynamoDB, and then publishes an
SNS notification containing the roll number, name, course and registration status.

## Configuration (environment variables)

| Variable        | Example                                              |
|-----------------|------------------------------------------------------|
| `AWS_REGION`    | `us-east-1`                                          |
| `ROLL_NO`       | your university roll number                          |
| `TABLE_NAME`    | `Students-<ROLL_NO>` (partition key `roll_no`, String) |
| `SNS_TOPIC_ARN` | ARN of `StudentRegistration-<ROLL_NO>`               |

No AWS keys are used in code. On EC2 the app gets credentials from the
`LabInstanceProfile` instance profile.

## Routes

- `GET /` – registration form
- `POST /register` – save the record (rejects duplicate roll numbers with 409) and send the SNS email
- `GET /health` – health check

## Run locally

```
pip install -r requirements.txt
python app.py          # http://localhost:5000
```

## Production (EC2)

Runs under systemd with gunicorn on port 80:
`gunicorn -w 2 -b 0.0.0.0:80 app:app`
