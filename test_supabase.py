import psycopg2
import os

print("Cadena de conexión:", os.environ["SUPABASE_URL"])
conn = psycopg2.connect(os.environ["SUPABASE_URL"])
cur = conn.cursor()
cur.execute("SELECT 1;")
print(cur.fetchone())
cur.close()
conn.close()