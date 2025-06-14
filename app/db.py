# app/db.py
from cs50 import SQL
import os

db = None

def init_db(app):
    global db
    db_path = os.path.join(app.instance_path, "grades.db")
    os.makedirs(app.instance_path, exist_ok=True)
    if not os.path.exists(db_path):
        open(db_path, 'a').close()
    db = SQL(f"sqlite:///{db_path}")
