#!/bin/bash

echo "Test script is running"
echo "Current directory: $(pwd)"
echo "Directory contents:"
ls -la
echo "Environment variables:"
env | grep -E "DATABASE|STATIC|DJANGO|PORT"






