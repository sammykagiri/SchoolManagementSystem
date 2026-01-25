#!/bin/bash
# Fix migration order issue in production
# communications.0002_initial was applied before receivables.0001_initial

echo "Step 1: Rolling back communications.0002_initial..."
python manage.py migrate communications 0001_initial

echo "Step 2: Applying receivables migrations..."
python manage.py migrate receivables

echo "Step 3: Re-applying communications.0002_initial..."
python manage.py migrate communications

echo "Step 4: Applying any remaining migrations..."
python manage.py migrate

echo "Done! Migration order has been fixed."
