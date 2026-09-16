#!/bin/bash
# Simple backup script for Smart Study System

# Configuration
BACKUP_DIR="./backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
APP_NAME="smart_study_system"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

echo "Starting backup of $APP_NAME..."
echo "Timestamp: $TIMESTAMP"

# Activate virtual environment and create backup
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    echo "Virtual environment activated."
else
    echo "Warning: Virtual environment not found at venv/bin/activate"
    echo "Make sure Django is installed and accessible."
fi

# Create education data backup with timestamp
OUTPUT_FILE="$BACKUP_DIR/${APP_NAME}_education_$TIMESTAMP.json"
echo "Dumping education data to $OUTPUT_FILE..."

python manage.py dump_education_data --output="$OUTPUT_FILE" --timestamp --include-users

# Check if backup was successful (look for files matching our pattern)
LATEST_BACKUP=$(ls -t "${BACKUP_DIR}/${APP_NAME}_education_${TIMESTAMP}"*.json 2>/dev/null | head -1)

if [ -n "$LATEST_BACKUP" ] && [ -f "$LATEST_BACKUP" ]; then
    FILE_SIZE=$(du -h "$LATEST_BACKUP" | cut -f1)
    echo "✓ Backup successful!"
    echo "  Location: $LATEST_BACKUP"
    echo "  Size: $FILE_SIZE"
else
    echo "✗ Backup failed!"
    exit 1
fi

# Optional: Also create a full database dump
# OUTPUT_FILE_FULL="$BACKUP_DIR/${APP_NAME}_full_$TIMESTAMP.json"
# echo "Dumping full database to $OUTPUT_FILE_FULL..."
# python manage.py dumpdata --all --output="$OUTPUT_FILE_FULL" --timestamp

deactivate 2>/dev/null || true
echo "Backup process completed."