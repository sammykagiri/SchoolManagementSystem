#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fees_management.settings')
django.setup()

from django.core.management import execute_from_command_line

# Run migrate command
execute_from_command_line(['manage.py', 'migrate'])
