
from getpass import getpass
from run import app
from app.models import User

with app.app_context():
    email = input("Email exacto: ").strip()
    password = getpass("Contraseña que intentas usar: ")

    user = User.query.filter_by(email=email).first()

    print("Usuario encontrado:", user is not None)

    if user:
        print("Cuenta activa:", user.is_active)
        print("Rol:", user.role.name if user.role else "Sin rol")
        print("Contraseña válida:", user.check_password(password))
