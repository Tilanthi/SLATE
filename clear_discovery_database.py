#!/usr/bin/env python3
"""
Manual Database Clearing Script for Fresh Discovery Start

This script safely clears the discovery database for a fresh start.
Run this manually if you want a completely clean slate.
"""

import sqlite3
import os
from datetime import datetime
from pathlib import Path

def clear_discovery_database():
    """Clear all discoveries from the database for fresh start."""

    db_path = "slate_core/slate_realistic_discoveries.db"

    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return False

    print(f"🔄 Clearing discovery database: {db_path}")

    # Create backup
    backup_path = f"slate_core/slate_realistic_discoveries_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    import shutil
    shutil.copy2(db_path, backup_path)
    print(f"✅ Backup created: {backup_path}")

    # Clear database
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()

        cleared_count = 0
        for (table_name,) in tables:
            try:
                cursor.execute(f"DELETE FROM {table_name}")
                deleted = cursor.rowcount
                cleared_count += deleted
                print(f"   ✅ Cleared {deleted} rows from {table_name}")
            except Exception as e:
                print(f"   ⚠️  Could not clear {table_name}: {e}")

        conn.commit()
        cursor.execute("VACUUM")

        # Verify clearing
        for (table_name,) in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"   📊 {table_name}: {count} rows remaining")

        conn.close()

        print(f"\n✅ Database clearing complete!")
        print(f"📊 Total rows cleared: {cleared_count}")
        print(f"💾 Backup preserved: {backup_path}")
        return True

    except Exception as e:
        print(f"❌ Error clearing database: {e}")
        return False

if __name__ == "__main__":
    print("🔄 SLATE Discovery Database Clearing")
    print("=" * 50)
    clear_discovery_database()
