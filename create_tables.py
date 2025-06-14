from app import create_app, db
from app.models import User, Grade, CustomGPA, UserSettings  # make sure all models are imported

app = create_app()

with app.app_context():
    db.create_all()
    print("✅ Tables created successfully.")
