
import os
import pymysql
from dotenv import load_dotenv

load_dotenv()

def initialize_database():
    host = os.getenv("MYSQL_HOST", "localhost")
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "")
    
    # Connect without DB to create it if missing
    connection = pymysql.connect(host=host, user=user, password=password, charset='utf8mb4')
    try:
        with connection.cursor() as cursor:
            cursor.execute("CREATE DATABASE IF NOT EXISTS smart_food_rescue_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        connection.commit()
    finally:
        connection.close()
        
    # Now execute schema script
    db = pymysql.connect(host=host, user=user, password=password, database="smart_food_rescue_db", charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
    try:
        with open("schema.sql", "r") as f:
            sql_script = f.read()
        with db.cursor() as cursor:
            for statement in sql_script.split(';'):
                if statement.strip():
                    cursor.execute(statement)
        db.commit()
        print("Database initialized successfully with all default tables and seed records!")
    except Exception as e:
        print(f"Error initializing database: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    initialize_database()