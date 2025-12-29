#!/bin/bash

echo "Starting deployment process..."

echo "Creating necessary directories..."
mkdir -p static
mkdir -p staticfiles
mkdir -p media

echo "Running migrations..."
python manage.py migrate --noinput
if [ $? -ne 0 ]; then
    echo "Migrations failed!"
    exit 1
fi
echo "Migrations completed successfully."

echo "Creating superuser if not exists..."
python manage.py create_superuser_if_not_exists
if [ $? -ne 0 ]; then
    echo "Superuser creation failed (this is OK if superuser already exists or password not set)!"
fi

echo "Collecting static files..."
python manage.py collectstatic --noinput
if [ $? -ne 0 ]; then
    echo "Static files collection failed!"
    exit 1
fi
echo "Static files collected successfully."

echo "Starting gunicorn..."
exec gunicorn school_management.wsgi:application --bind 0.0.0.0:$PORT --log-file - --timeout 240

