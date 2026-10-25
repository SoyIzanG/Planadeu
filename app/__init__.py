
"""
Sitio web de la liga: aplicación Flask.
Sistema de gestión de una liga de fútbol.
"""

from flask import Flask
from flask_migrate import Migrate

from app.config import config
from app.extensions import db, login_manager, csrf, bcrypt


def create_app(config_name: str = "development") -> Flask:
    """Crea y configura una instancia de la aplicación."""

    app = Flask(__name__)

    # Cargar la configuración.
    app.config.from_object(config[config_name])

    # Inicializar extensiones.
    db.init_app(app)
    Migrate(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    bcrypt.init_app(app)

    # Configurar Cloudinary en producción.
    if app.config.get("USE_CLOUDINARY"):
        import cloudinary

        cloudinary.config(
            cloud_name=app.config.get("CLOUDINARY_CLOUD_NAME"),
            api_key=app.config.get("CLOUDINARY_API_KEY"),
            api_secret=app.config.get("CLOUDINARY_API_SECRET"),
        )

    # Registrar visitas.
    @app.before_request
    def registrar_visita():
        from app.services.visitor_service import track_visitor
        track_visitor()

    # Configurar el inicio de sesión.
    from app.models import User
    from flask_login import set_login_view

    with app.app_context():
        set_login_view("auth.login")

    login_manager.login_message = "Inicia sesión para acceder a esta página."
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def cargar_usuario(user_id):
        return User.query.get(int(user_id))

    # Registrar las rutas de cada sección.
    registrar_blueprints(app)

    # Registrar los controladores de errores.
    registrar_manejadores_errores(app)

    # Servir archivos subidos.
    from flask import send_from_directory
    from app.config import (
        TEAM_LOGOS_FOLDER,
        PLAYER_PHOTOS_FOLDER,
        GALLERY_FOLDER,
    )

    @app.route("/uploads/team_logos/<path:filename>")
    def logo_equipo(filename):
        return send_from_directory(TEAM_LOGOS_FOLDER, filename)

    @app.route("/uploads/player_photos/<path:filename>")
    def foto_jugador(filename):
        return send_from_directory(PLAYER_PHOTOS_FOLDER, filename)

    @app.route("/uploads/gallery/<path:filename>")
    def imagen_galeria(filename):
        return send_from_directory(GALLERY_FOLDER, filename)

    # Resolver direcciones de imágenes locales o de Cloudinary.
    from flask import url_for

    @app.template_filter("asset_url")
    def filtro_url_recurso(identifier, asset_type="team"):
        if not identifier:
            return None

        if identifier.startswith(("http://", "https://")):
            return identifier

        return url_for(
            "logo_equipo" if asset_type == "team" else "foto_jugador",
            filename=identifier,
        )

    registrar_comandos(app)

    return app
def registrar_blueprints(app: Flask) -> None:
    """Registra las rutas de las diferentes secciones."""

    from app.blueprints.auth import auth_bp
    from app.blueprints.admin import admin_bp
    from app.blueprints.league import league_bp
    from app.blueprints.teams import teams_bp
    from app.blueprints.players import players_bp
    from app.blueprints.matches import matches_bp
    from app.blueprints.gallery import gallery_bp
    from app.blueprints.fan import fan_bp
    from app.api import api_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(league_bp, url_prefix="/league")
    app.register_blueprint(teams_bp, url_prefix="/teams")
    app.register_blueprint(players_bp, url_prefix="/players")
    app.register_blueprint(matches_bp, url_prefix="/matches")
    app.register_blueprint(gallery_bp, url_prefix="/gallery")
    app.register_blueprint(fan_bp, url_prefix="/fan")
    app.register_blueprint(api_bp, url_prefix="/api")

    # Página principal.
    @app.route("/")
    def index():
        from flask import render_template
        return render_template("home.html")


def registrar_manejadores_errores(app: Flask) -> None:
    """Registra las páginas de error."""

    from flask import render_template

    @app.errorhandler(404)
    def error_no_encontrado(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def error_interno(error):
        db.session.rollback()
        return render_template("errors/500.html"), 500


def registrar_comandos(app: Flask) -> None:
    """Registra los comandos de Flask."""

    @app.cli.command("init-db")
    def inicializar_base_datos():
        """Inicializa la base de datos."""
        db.create_all()
        print("Base de datos inicializada.")

    @app.cli.command("create-admin")
    def crear_administrador():
        """Crea una cuenta de administrador."""

        from app.models import User, Role
        from getpass import getpass

        email = input("Correo del administrador: ").strip()
        username = input("Nombre de usuario: ").strip()
        password = getpass("Contraseña del administrador: ")

        if User.query.filter_by(email=email).first():
            print("Ya existe una cuenta con ese correo.")
            return

        if User.query.filter_by(username=username).first():
            print("Ya existe ese nombre de usuario.")
            return

        admin_role = Role.query.filter_by(name="Admin").first()

        if not admin_role:
            admin_role = Role(name="Admin")
            db.session.add(admin_role)
            db.session.commit()

        user = User()
        user.email = email
        user.username = username
        user.role_id = admin_role.id
        user.password = password

        db.session.add(user)
        db.session.commit()

        print(f"Cuenta de administrador creada: {username}")

