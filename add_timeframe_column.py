#!/usr/bin/env python3
"""
Update the discovery engine to support multiple timeframes.
This script modifies the database schema and updates the discovery cycle.
"""

import sqlite3
from pathlib import Path

# Add timeframe column to database
db_path = "slate_core/slate_realistic_discoveries.db"

print("Adding timeframe column to database schema...")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Add timeframe column if it doesn't exist
try:
    cursor.execute("ALTER TABLE edge_discoveries ADD COLUMN timeframe TEXT")
    print("✓ Added timeframe column")
except sqlite3.OperationalError as e:
    if "duplicate column" in str(e):
        print("✓ Timeframe column already exists")
    else:
        print(f"Error: {e}")

conn.commit()
conn.close()

print("\nDatabase schema updated to support multiple timeframes")
print("\nTimeframes to test: 1m, 5m, 10m, 15m, 30m, 1h, 4h, 8h, 12h, 1d")
