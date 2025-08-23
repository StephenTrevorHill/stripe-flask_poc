# AWS Lambda → SQS → Lambda POC (staging + prod)

Minimal free‑tier stack for a Stripe test webhook POC.
Local dev = unit tests only. Integration tests run in `staging`.

## Quickstart

1) Create a venv and run tests locally:
```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
```

2) Set Stripe secret in SSM (staging) and deploy:
```bash
aws ssm put-parameter --name /app/staging/STRIPE_SECRET --type SecureString --value whsec_XXXX --overwrite
sam build -t infra/template.yaml
sam deploy --guided --stack-name webhook-staging --parameter-overrides Stage=staging --capabilities CAPABILITY_IAM
```

3) Copy the API endpoint from stack outputs and configure a Stripe **test** webhook to POST there, then send a test event.

Notes:
- No VPC/NAT/ALB; stays inside free tiers.
- DynamoDB table key: `eventId` (Stripe event id), with GSI on `tenantId` + `createdAt`.
- Logs go to CloudWatch via stdout.
