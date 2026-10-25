"""
Flask extensions - initialized here, bound to app in factory.
Prevents circular imports by deferring extension initialization.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_bcrypt import Bcrypt

# Database ORM
db = SQLAlchemy()

# Authentication
login_manager = LoginManager()
bcrypt = Bcrypt()

# Security
csrf = CSRFProtect()
