from run import app
from app import db
from app.models import User

app.app_context().push()

users = User.query.all()
print(users)
