import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    print("Checking library imports...")
    try:
        import fastapi
        import sqlalchemy
        import lancedb
        import pyarrow
        import fitz
        print("[OK] All libraries imported successfully!")
    except ImportError as e:
        print(f"[ERROR] Import failed: {str(e)}")
        sys.exit(1)

def test_database():
    print("\nTesting SQLite database setup...")
    try:
        from app.database.db import engine, SessionLocal
        from app.database import models
        
        # Test engine connection
        conn = engine.connect()
        conn.close()
        print("[OK] SQLite Connection Successful!")
        
        # Test Session creation
        db = SessionLocal()
        db.close()
        print("[OK] SQLite Session Creation Successful!")
    except Exception as e:
        print(f"[ERROR] Database test failed: {str(e)}")
        sys.exit(1)

def test_vector_db():
    print("\nTesting LanceDB vector storage...")
    try:
        import lancedb
        from app.config import settings
        
        db = lancedb.connect(settings.LANCEDB_DIR)
        print(f"[OK] Connected to LanceDB at: {settings.LANCEDB_DIR}")
        print(f"Existing tables: {db.table_names()}")
    except Exception as e:
        print(f"[ERROR] LanceDB test failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    print("=== Second Brain OS Backend Verification ===")
    test_imports()
    test_database()
    test_vector_db()
    print("===========================================")
    print("Success: Backend foundations are valid!")
