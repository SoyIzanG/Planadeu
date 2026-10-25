
from run import app
from app.models import User, Role

with app.app_context():
    print("USUARIOS:")
    for user in User.query.all():
        print(user.username, "|", user.email, "| rol:", user.role_id)

    print("\nROLES:")
    for role in Role.query.all():
        print(role.id, "|", role.name)