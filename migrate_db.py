"""
Database migration script to add new columns for folders, trash, and favorites.
Run this script once to update your existing database.
"""
import sqlite3
import os
from app.config import get_settings

settings = get_settings()

# Extract database path from DATABASE_URL
# Format: sqlite:///./cloud_drive.db
db_url = settings.database_url
if db_url.startswith("sqlite:///"):
    db_path = db_url.replace("sqlite:///", "")
else:
    db_path = "cloud_drive.db"

if not os.path.exists(db_path):
    print(f"Database file {db_path} not found. It will be created on first run.")
    exit(0)

print(f"Connecting to database: {db_path}")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # Check existing columns in files table
    cursor.execute("PRAGMA table_info(files)")
    existing_columns = [row[1] for row in cursor.fetchall()]
    print(f"Existing columns in 'files' table: {existing_columns}")
    
    # Add folder_id if it doesn't exist
    if 'folder_id' not in existing_columns:
        print("Adding 'folder_id' column to 'files' table...")
        cursor.execute("ALTER TABLE files ADD COLUMN folder_id INTEGER")
        print("✓ Added folder_id column")
    else:
        print("✓ folder_id column already exists")
    
    # Add is_trashed if it doesn't exist
    if 'is_trashed' not in existing_columns:
        print("Adding 'is_trashed' column to 'files' table...")
        cursor.execute("ALTER TABLE files ADD COLUMN is_trashed BOOLEAN DEFAULT 0")
        print("✓ Added is_trashed column")
    else:
        print("✓ is_trashed column already exists")
    
    # Add trashed_at if it doesn't exist
    if 'trashed_at' not in existing_columns:
        print("Adding 'trashed_at' column to 'files' table...")
        cursor.execute("ALTER TABLE files ADD COLUMN trashed_at DATETIME")
        print("✓ Added trashed_at column")
    else:
        print("✓ trashed_at column already exists")
    
    # Check if folders table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='folders'")
    if not cursor.fetchone():
        print("Creating 'folders' table...")
        cursor.execute("""
            CREATE TABLE folders (
                id INTEGER NOT NULL PRIMARY KEY,
                name VARCHAR NOT NULL,
                owner_id INTEGER NOT NULL,
                parent_id INTEGER,
                created_at DATETIME,
                FOREIGN KEY(owner_id) REFERENCES users (id),
                FOREIGN KEY(parent_id) REFERENCES folders (id)
            )
        """)
        print("✓ Created folders table")
    else:
        print("✓ folders table already exists")
    
    # Check if favorites table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='favorites'")
    if not cursor.fetchone():
        print("Creating 'favorites' table...")
        cursor.execute("""
            CREATE TABLE favorites (
                id INTEGER NOT NULL PRIMARY KEY,
                file_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                created_at DATETIME,
                FOREIGN KEY(file_id) REFERENCES files (id),
                FOREIGN KEY(user_id) REFERENCES users (id)
            )
        """)
        print("✓ Created favorites table")
    else:
        print("✓ favorites table already exists")
    
    # Check if activity_logs table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='activity_logs'")
    if not cursor.fetchone():
        print("Creating 'activity_logs' table...")
        cursor.execute("""
            CREATE TABLE activity_logs (
                id INTEGER NOT NULL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                action VARCHAR NOT NULL,
                file_id INTEGER,
                details VARCHAR,
                created_at DATETIME,
                FOREIGN KEY(user_id) REFERENCES users (id),
                FOREIGN KEY(file_id) REFERENCES files (id)
            )
        """)
        print("✓ Created activity_logs table")
    else:
        print("✓ activity_logs table already exists")
    
    conn.commit()
    print("\n✅ Migration completed successfully!")
    
except Exception as e:
    conn.rollback()
    print(f"\n❌ Error during migration: {e}")
    raise
finally:
    conn.close()

