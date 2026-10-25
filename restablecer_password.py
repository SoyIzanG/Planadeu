
from getpass import getpass
from app import create_app
from app.extensions import db
from app.models import User

app = create_app("development")

with app.app_context():
    email = input("Email exacto de la cuenta: ").strip()
    user = User.query.filter_by(email=email).first()

    if user is None:
        print("No existe ninguna cuenta con ese email.")
    else:
        password = getpass("Introduce la nueva contraseña: ")
        confirm = getpass("Repite la nueva contraseña: ")

        if len(password) < 12:
            print("La contraseña debe tener al menos 12 caracteres.")
        elif password != confirm:
            print("Las contraseñas no coinciden.")
        else:
            user.password = password
            db.session.commit()
            print("Contraseña actualizada correctamente.")
            print("Usuario:", user.username)
