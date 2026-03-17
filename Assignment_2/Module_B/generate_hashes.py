"""
Password Hash Generator
Campus Trading Application - Module B

Run this ONCE after setting up the database to replace the
placeholder password hashes with real bcrypt hashes.

Usage:
    python generate_hashes.py

This will update:
  - admin        → password: admin123
  - amal.perera  → password: password123
  - nimali.fernando
  - kavindu.silva
  - ravindu.bandara
"""

import os
import sys
import bcrypt

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def main():
    print("Generating bcrypt password hashes...\n")

    credentials = [
        ('admin',            'admin123'),
        ('amal.perera',      'password123'),
        ('nimali.fernando',  'password123'),
        ('kavindu.silva',    'password123'),
        ('ravindu.bandara',  'password123'),
    ]

    hashes = {}
    for username, password in credentials:
        h = hash_password(password)
        hashes[username] = h
        print(f"  {username}: {h[:40]}...")

    # Try to update the database directly
    try:
        from dotenv import load_dotenv
        load_dotenv()

        import pymysql
        conn = pymysql.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', 3306)),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', ''),
            database=os.getenv('DB_NAME', 'CampusTrading'),
        )
        cursor = conn.cursor()

        for username, password in credentials:
            h = hashes[username]
            cursor.execute(
                "UPDATE `User` SET PasswordHash = %s WHERE Username = %s",
                (h, username)
            )
            rows = cursor.rowcount
            print(f"  Updated {username}: {rows} row(s)")

        conn.commit()
        cursor.close()
        conn.close()
        print("\n✅ All password hashes updated in database!")
        print("\nYou can now log in with:")
        print("  admin / admin123")
        print("  amal.perera / password123")

    except ImportError:
        print("\n⚠️  Could not connect to database (pymysql not installed or .env missing).")
        print("Run the following SQL manually:\n")
        for username, password in credentials:
            h = hashes[username]
            print(f"UPDATE `User` SET PasswordHash = '{h}' WHERE Username = '{username}';")

    except Exception as e:
        print(f"\n⚠️  Database error: {e}")
        print("Run the following SQL manually:\n")
        for username, password in credentials:
            h = hashes[username]
            print(f"UPDATE `User` SET PasswordHash = '{h}' WHERE Username = '{username}';")

if __name__ == '__main__':
    main()
