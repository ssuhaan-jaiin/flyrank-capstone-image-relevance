from database import get_connection

PAIRS = [(12,35),(12,33),(14,46),(23,28),(23,32),(2,15),(2,3),(10,17),(10,50)]

conn = get_connection()
for expected, got in PAIRS:
    e = conn.execute("SELECT subject FROM images WHERE id=%s", (expected,)).fetchone()
    g = conn.execute("SELECT subject FROM images WHERE id=%s", (got,)).fetchone()
    print(f"expected {expected}={e['subject']!r}  got {got}={g['subject']!r}")
conn.close()