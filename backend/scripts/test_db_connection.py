import sys
import os
import pymysql
from dotenv import load_dotenv

# Load .env file from root
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(project_root, ".env"))

DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_NAME = os.getenv("DB_NAME", "placematch_db")

def test_and_create_db():
    print(f"[*] Attempting connection to MySQL server at {DB_HOST}:{DB_PORT} as user '{DB_USER}'...")
    try:
        connection = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor
        )
        print(" -> Successfully connected to MySQL Server!")
        
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
            print(f" -> Database '{DB_NAME}' verified / created successfully!")
            
        connection.close()
        print("\nAll database pre-checks passed! You are ready for SQLAlchemy models.")
        return True
    except pymysql.MySQLError as e:
        print(f"\n[!] MySQL Connection Error: {e}")
        print("[!] Please verify:")
        print("    1. MySQL service is running on Windows (Services -> MySQL80).")
        print("    2. Your password in the '.env' file matches your MySQL root password.")
        return False

if __name__ == "__main__":
    success = test_and_create_db()
    if not success:
        sys.exit(1)
