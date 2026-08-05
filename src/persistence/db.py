# src/db_config.py
import os
import psycopg2
from dotenv import load_dotenv

# Ensure environment variables are loaded when this utility is accessed
load_dotenv()

def get_db_connection():
    """
    Establishes and returns a live connection to your Supabase instance 
    using parameters managed inside your local .env file.
    """
    try:
        conn = psycopg2.connect(
            host=os.getenv("SUPABASE_URL"),
            database=os.getenv("SUPABASE_DB_NAME", "postgres"),
            user=os.getenv("SUPABASE_USER"),
            password=os.getenv("SUPABASE_PASSWORD"),
            port=os.getenv("SUPABASE_PORT", "6543")
        )
        return conn
    except Exception as e:
        print(f"❌ Database Connection Engine Critical Failure: {e}")
        raise e
