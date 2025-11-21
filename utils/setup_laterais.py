import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from database import get_db_connection, close_db_connection

def inspect_and_create():
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database")
        return

    try:
        cursor = conn.cursor()
        
        # Inspect acf_atletas
        print("Inspecting acf_atletas structure...")
        cursor.execute("SELECT * FROM acf_atletas LIMIT 1")
        columns = [desc[0] for desc in cursor.description]
        print(f"Columns in acf_atletas: {columns}")
        
        # Create laterais_esquerdos table
        print("\nCreating laterais_esquerdos table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS laterais_esquerdos (
                atleta_id INTEGER PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        print("Table laterais_esquerdos created (or already exists).")
        
        # Verify creation
        cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'laterais_esquerdos')")
        exists = cursor.fetchone()[0]
        print(f"Table exists: {exists}")

    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        close_db_connection(conn)

if __name__ == "__main__":
    inspect_and_create()
