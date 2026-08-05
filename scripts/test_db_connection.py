import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()

try:
    conn = psycopg2.connect(
        host=os.environ.get("DB_HOST"),
        database=os.environ.get("DB_NAME"),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD"),
        port=os.environ.get("DB_PORT"),
    )
    cursor = conn.cursor()
    cursor.execute("SELECT version();")
    print(f"Connected to live Supabase Instance! Engine Details: {cursor.fetchone()}")
    cursor.close()
    conn.close()
except Exception as e:
    print(f"Connection failed: {e}")
