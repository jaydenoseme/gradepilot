from sqlalchemy import text
from app import create_app, db

app = create_app()

with app.app_context():
    sql = text('ALTER TABLE user ADD COLUMN a_plus FLOAT DEFAULT 4.0')
    try:
        with db.engine.connect() as conn:
            conn.execute(sql)
        print("Column added successfully")
    except Exception as e:
        print("Error occurred:", e)
