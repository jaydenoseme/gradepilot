from app import app, db
from sqlalchemy import text

with app.app_context():
    with db.engine.connect() as connection:
        try:
            connection.execute(text('ALTER TABLE user ADD COLUMN a_plus FLOAT DEFAULT 4.0'))
            connection.execute(text('ALTER TABLE user ADD COLUMN a FLOAT DEFAULT 4.0'))
            connection.execute(text('ALTER TABLE user ADD COLUMN a_minus FLOAT DEFAULT 3.7'))
            connection.execute(text('ALTER TABLE user ADD COLUMN b_plus FLOAT DEFAULT 3.3'))
            connection.execute(text('ALTER TABLE user ADD COLUMN b FLOAT DEFAULT 3.0'))
            connection.execute(text('ALTER TABLE user ADD COLUMN b_minus FLOAT DEFAULT 2.7'))
            connection.execute(text('ALTER TABLE user ADD COLUMN c_plus FLOAT DEFAULT 2.3'))
            connection.execute(text('ALTER TABLE user ADD COLUMN c FLOAT DEFAULT 2.0'))
            connection.execute(text('ALTER TABLE user ADD COLUMN c_minus FLOAT DEFAULT 1.7'))
            connection.execute(text('ALTER TABLE user ADD COLUMN d_plus FLOAT DEFAULT 1.3'))
            connection.execute(text('ALTER TABLE user ADD COLUMN d FLOAT DEFAULT 1.0'))
            connection.execute(text('ALTER TABLE user ADD COLUMN d_minus FLOAT DEFAULT 0.7'))
            connection.execute(text('ALTER TABLE user ADD COLUMN f FLOAT DEFAULT 0.0'))
            connection.execute(text('ALTER TABLE user ADD COLUMN weight_regular FLOAT DEFAULT 0.0'))
            connection.execute(text('ALTER TABLE user ADD COLUMN weight_honors FLOAT DEFAULT 0.5'))
            connection.execute(text('ALTER TABLE user ADD COLUMN weight_ap FLOAT DEFAULT 1.0'))
            connection.execute(text('ALTER TABLE user ADD COLUMN weight_ib FLOAT DEFAULT 1.0'))
            connection.execute(text('ALTER TABLE user ADD COLUMN weight_de FLOAT DEFAULT 1.0'))
            connection.execute(text('ALTER TABLE user ADD COLUMN gpa_cap FLOAT'))
            print("✅ Columns added successfully.")
        except Exception as e:
            print("⚠️ Error occurred:", e)
