#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   STAGE=staging ./tools/redrive_dlq.sh [--rate 50]
# Env it uses:
#   AWS_PROFILE (defaults to current), AWS_REGION (defaults to current), STAGE (required)

RATE=""
if [[ "${1:-}" == "--rate" && -n "${2:-}" ]]; then
  RATE="--max-number-of-messages-per-second ${2}"
fi

: "${STAGE:?Set STAGE (e.g., STAGE=staging)}"

# Queue names per our SAM template
SRC_NAME="events-${STAGE}"
DLQ_NAME="events-${STAGE}-dlq"

echo "🔎 Resolving queue ARNs for STAGE=${STAGE}…"
SRC_URL=$(aws sqs get-queue-url --queue-name "${SRC_NAME}" --query QueueUrl --output text)
DLQ_URL=$(aws sqs get-queue-url --queue-name "${DLQ_NAME}" --query QueueUrl --output text)
SRC_ARN=$(aws sqs get-queue-attributes --queue-url "${SRC_URL}" --attribute-names QueueArn --query 'Attributes.QueueArn' --output text)
DLQ_ARN=$(aws sqs get-queue-attributes --queue-url "${DLQ_URL}" --attribute-names QueueArn --query 'Attributes.QueueArn' --output text)

echo "   Source: ${SRC_NAME} (${SRC_ARN})"
echo "   DLQ:    ${DLQ_NAME} (${DLQ_ARN})"

echo "▶️  Starting message move task (DLQ → Source) ${RATE}"
# If you omit --destination-arn, SQS redrives back to the *original source queue(s)* automatically.
# Here we pin to our known source queue for clarity.
OUT=$(aws sqs start-message-move-task --source-arn "${DLQ_ARN}" --destination-arn "${SRC_ARN}" ${RATE} --output json)
TASK=$(jq -r '.TaskHandle' <<<"${OUT}" 2>/dev/null || echo "")
echo "   TaskHandle: ${TASK:-<none-returned>}"

echo "⏳ Polling task status (ctrl+c to stop)…"
while true; do
  STATUS=$(aws sqs list-message-move-tasks --source-arn "${DLQ_ARN}" --max-results 1 \
           --query 'Results[0].Status' --output text 2>/dev/null || echo "UNKNOWN")
  MOVED=$(aws sqs list-message-move-tasks --source-arn "${DLQ_ARN}" --max-results 1 \
           --query 'Results[0].ApproximateNumberOfMessagesMoved' --output text 2>/dev/null || echo "0")
  TODO=$(aws sqs list-message-move-tasks --source-arn "${DLQ_ARN}" --max-results 1 \
           --query 'Results[0].ApproximateNumberOfMessagesToMove' --output text 2>/dev/null || echo "0")

  echo "   Status=${STATUS}  Moved=${MOVED}  Remaining≈${TODO}"
  [[ "${STATUS}" == "COMPLETED" || "${STATUS}" == "FAILED" || "${STATUS}" == "CANCELLED" ]] && break
  sleep 2
done