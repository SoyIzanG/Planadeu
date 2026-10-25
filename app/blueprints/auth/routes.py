
"""
Auth routes - login, logout.
"""

from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user

from app.blueprints.auth import auth_bp
from app.extensions import db
from app.models import User


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Login page and form handler."""

    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        # Buscar el correo sin distinguir mayúsculas y minúsculas.
        user = User.query.filter(
            db.func.lower(User.email) == email.lower()
        ).first()

        # Diagnóstico temporal: nunca imprimir la contraseña.
        print("LOGIN DEBUG - correo:", repr(email))
        print("LOGIN DEBUG - usuario encontrado:", bool(user))
        print(
            "LOGIN DEBUG - contraseña válida:",
            user.check_password(password) if user else False
        )
        print(
            "LOGIN DEBUG - cuenta activa:",
            user.is_active if user else None
        )

        if user and user.check_password(password):
            if user.is_active:
                login_result = login_user(
                    user,
                    remember=bool(request.form.get("remember"))
                )

                print(
                    "LOGIN DEBUG - login_user aceptado:",
                    login_result
                )

                if login_result:
                    next_url = request.args.get("next") or url_for(
                        "admin.dashboard"
                    )
                    return redirect(next_url)

                flash(
                    "No se ha podido iniciar sesión. "
                    "Comprueba la configuración de autenticación.",
                    "danger"
                )
            else:
                flash("La cuenta está desactivada.", "danger")
        else:
            flash("Correo o contraseña incorrectos.", "danger")

    return render_template("auth/login.html")


@auth_bp.route("/logout")
def logout():
    """Logout user."""
    logout_user()
    flash("Has cerrado sesión.", "info")
    return redirect(url_for("index"))

