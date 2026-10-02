from dotenv import load_dotenv
import os
import psycopg2

load_dotenv("/opt/prospectlab/.env")
conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM entreprises")
print("ENTREPRISES", cur.fetchone()[0])
conn.close()
print("DB_OK")
