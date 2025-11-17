#!/bin/bash

read -p "Enter Authorization header value [ZIMMERMAN]: " AUTH_HEADER
AUTH_HEADER=${AUTH_HEADER:-ZIMMERMAN}
# Set up cron job to run at 9:30 AM daily (9:30 based on initial definition)
CRON_JOB="30 9 * * * curl -s -H \"Authorization: $AUTH_HEADER\" http://localhost:5000/backup/update-tgf-datasets"

(crontab -l 2>/dev/null | grep -F "$CRON_JOB") >/dev/null
if [ $? -ne 0 ]; then
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    echo "✅ Cron job added."
else
    echo "ℹ️ Cron job already exists."
fi
