
from run import app as run_app
from app import create_app
from app.models import User


def db_uri(app):
    return app.config.get("SQLALCHEMY_DATABASE_URI", "(no encontrada)")


apps = [
    ("Servidor web (run.py)", run_app),
    ("Aplicación development", create_app("development")),
]

for nombre, app in apps:
    with app.app_context():
        print("\n---", nombre, "---")
        print("Base de datos:", db_uri(app))

        for usuario in User.query.all():
            print(
                "Email:", repr(usuario.email),
                "| Activo:", usuario.is_active
            )
