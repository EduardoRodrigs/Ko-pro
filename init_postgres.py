import os
import sys

# Add current directory to path so database.py can be imported
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import init_db, engine

def main():
    print("=== PostgreSQL Initialization Tool ===")
    
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("Warning: DATABASE_URL environment variable is not defined.")
        print("Falling back to local SQLite database settings.")
    else:
        print(f"Connecting to database using connection string...")
        
    try:
        # Run init_db which sets up tables and populates default products
        print("Initializing tables and populating default products...")
        init_db()
        print("Success! Database initialized successfully.")
    except Exception as e:
        print(f"Error initializing database: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
