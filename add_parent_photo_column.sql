-- SQL script to manually add the photo column to core_parent table
-- This is a temporary workaround until migrations are run on production
-- Run this on your production database (Railway PostgreSQL)
--
-- To run this on Railway:
-- 1. Go to your Railway project dashboard
-- 2. Click on your PostgreSQL database service
-- 3. Go to the "Data" or "Query" tab
-- 4. Paste and execute this SQL

-- Check if column already exists before adding
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_schema = 'public'
        AND table_name = 'core_parent' 
        AND column_name = 'photo'
    ) THEN
        -- ImageField in Django translates to VARCHAR(100) in PostgreSQL
        ALTER TABLE core_parent 
        ADD COLUMN photo VARCHAR(100) NULL;
        
        RAISE NOTICE 'Column photo added successfully to core_parent table';
    ELSE
        RAISE NOTICE 'Column photo already exists in core_parent table';
    END IF;
END $$;
