#!/bin/bash
# Force Python version check and install
echo "Checking Python version..."
python --version

# Install dependencies
pip install -r requirements.txt

# Verify psycopg2 installation
echo "Verifying psycopg2 installation..."
python -c "import psycopg2; print('psycopg2 installed successfully')"
