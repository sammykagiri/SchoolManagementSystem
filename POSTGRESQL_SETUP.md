# PostgreSQL Database Setup Guide

This guide will help you set up PostgreSQL for the School Management System.

## Prerequisites

1. **Install PostgreSQL** on your system:
   - **Windows**: Download from [PostgreSQL Downloads](https://www.postgresql.org/download/windows/)
   - **macOS**: `brew install postgresql` or download from PostgreSQL website
   - **Linux**: `sudo apt-get install postgresql postgresql-contrib` (Ubuntu/Debian) or use your distribution's package manager

2. **Verify Installation**:
   ```bash
   psql --version
   ```

## Database Setup Steps

### 1. Create PostgreSQL Database and User

Open PostgreSQL command line (psql) or pgAdmin and run:

```sql
-- Connect to PostgreSQL as superuser
-- Windows: Open "SQL Shell (psql)" from Start Menu
-- Or use: psql -U postgres

-- Create database
CREATE DATABASE school_management_db;

-- Create user (optional, you can use 'postgres' user for development)
CREATE USER school_user WITH PASSWORD 'your_password_here';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE school_management_db TO school_user;

-- For PostgreSQL 15+, you may need to grant schema privileges
\c school_management_db
GRANT ALL ON SCHEMA public TO school_user;
```

### 2. Install Python Dependencies

Install the PostgreSQL adapter for Python:

```bash
pip install -r requirements.txt
```

This will install `psycopg2-binary` which is the PostgreSQL adapter for Django.

### 3. Configure Environment Variables

Create or update your `.env` file in the project root with the following variables:

```env
# Database Configuration
DB_NAME=school_management_db
DB_USER=postgres
DB_PASSWORD=your_password_here
DB_HOST=localhost
DB_PORT=5432

# Other existing variables...
SECRET_KEY=your-secret-key-here
DEBUG=True
```

**Note**: Replace `your_password_here` with your actual PostgreSQL password.

### 4. Run Migrations

After setting up the database, run Django migrations:

```bash
python manage.py migrate
```

This will create all the necessary tables in your PostgreSQL database.

### 5. Create Superuser (Optional)

If you need to create an admin user:

```bash
python manage.py createsuperuser
```

## Testing the Connection

You can test the database connection by running:

```bash
python manage.py dbshell
```

This should open a PostgreSQL shell if the connection is successful.

## Troubleshooting

### Connection Refused Error

- Ensure PostgreSQL service is running:
  - **Windows**: Check Services (services.msc) for "postgresql-x64-XX"
  - **macOS/Linux**: `sudo systemctl status postgresql` or `brew services list`

### Authentication Failed

- Verify the username and password in your `.env` file
- Check PostgreSQL's `pg_hba.conf` file for authentication settings
- For local development, you may need to set `trust` authentication in `pg_hba.conf`

### Database Does Not Exist

- Make sure you've created the database using the SQL commands above
- Verify the database name in your `.env` file matches the created database

### Port Already in Use

- Check if PostgreSQL is running on a different port
- Update `DB_PORT` in your `.env` file accordingly
- Default PostgreSQL port is 5432

## Switching Back to SQLite (if needed)

If you need to switch back to SQLite for any reason, update `settings.py`:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
```

## Production Considerations

For production environments:

1. Use strong passwords
2. Restrict database user permissions (only grant what's needed)
3. Use connection pooling
4. Enable SSL connections
5. Regularly backup your database
6. Monitor database performance

## Additional Resources

- [Django PostgreSQL Documentation](https://docs.djangoproject.com/en/5.2/ref/databases/#postgresql-notes)
- [PostgreSQL Official Documentation](https://www.postgresql.org/docs/)
