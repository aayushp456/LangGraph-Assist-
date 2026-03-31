#!/bin/bash

# CSV Import Script

echo "📥 CSV Data Import Utility"
echo "=" * 60
echo ""

# Load CSV path from .env
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

CSV_PATH=${CSV_IMPORT_PATH:-"/Users/aayushpatel/Downloads/customer_support_tickets.csv"}

echo "CSV File: $CSV_PATH"
echo ""

# Check if file exists
if [ ! -f "$CSV_PATH" ]; then
    echo "❌ CSV file not found at: $CSV_PATH"
    echo ""
    echo "Please update CSV_IMPORT_PATH in .env file or provide path as argument:"
    echo "  ./import_data.sh /path/to/your/file.csv"
    exit 1
fi

# Use provided path if given as argument
if [ ! -z "$1" ]; then
    CSV_PATH="$1"
fi

echo "🚀 Starting import..."
python backend/scripts/import_csv.py --file "$CSV_PATH" --batch-size 100

echo ""
echo "✅ Import complete!"
