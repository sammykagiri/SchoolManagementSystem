#!/bin/bash

echo "Starting deployment process..."

echo "Running migrations..."
python manage.py migrate
if [ $? -ne 0 ]; then
    echo "Migrations failed!"
    exit 1
fi
echo "Migrations completed successfully."

echo "Creating staticfiles directory..."
mkdir -p staticfiles

echo "Collecting static files..."
python manage.py collectstatic --noinput
if [ $? -ne 0 ]; then
    echo "Static files collection failed!"
    exit 1
fi
echo "Static files collected successfully."

echo "Starting gunicorn..."
exec gunicorn school_management.wsgi:application --bind 0.0.0.0:$PORT --log-file - --timeout 240

