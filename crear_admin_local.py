
from getpass import getpass

from run import app
from app.extensions import db
from app.models import User, Role

with app.app_context():
    email = input("Email del administrador: ").strip()
    username = input("Nombre de usuario: ").strip()
    password = getpass("Contraseña nueva: ")

    if not email or not username or not password:
        raise SystemExit("Error: no dejes campos vacíos.")

    if User.query.filter_by(email=email).first():
        raise SystemExit("Error: ese email ya existe.")

    if User.query.filter_by(username=username).first():
        raise SystemExit("Error: ese nombre de usuario ya existe.")

    try:
        role = Role.query.filter_by(name="Admin").first()

        if role is None:
            role = Role(name="Admin")
            db.session.add(role)
            db.session.flush()

        user = User(
            email=email,
            username=username,
            is_active=True,
            role_id=role.id
        )
        user.password = password

        db.session.add(user)
        db.session.commit()

        print("Administrador creado correctamente.")

    except Exception:
        db.session.rollback()
        raise
