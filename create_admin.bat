@echo off
REM Create Admin User Script for Windows

if "%~1"=="" (
    echo Usage: create_admin.bat ^<DATABASE_URL^> [email] [username] [password]
    echo.
    echo Example:
    echo   create_admin.bat "your-database-url" admin@league.com admin Admin123!
    echo.
    echo Default credentials if not specified:
    echo   Email: admin@league.com
    echo   Username: admin
    echo   Password: Admin123!
    pause
    exit /b 1
)

set DATABASE_URL=%~1
set EMAIL=%~2
if "%EMAIL%"=="" set EMAIL=admin@league.com
set USERNAME=%~3
if "%USERNAME%"=="" set USERNAME=admin
set PASSWORD=%~4
if "%PASSWORD%"=="" set PASSWORD=Admin123!

echo === Creating Admin User ===
echo.
echo Database URL: %DATABASE_URL:~0,50%...
echo Email: %EMAIL%
echo Username: %USERNAME%
echo Password: %PASSWORD%

REM Create admin user
python -c "
import os
os.environ['DATABASE_URL'] = '%DATABASE_URL%'

from app import create_app
from app.extensions import db
from app.models import User, Role

app = create_app('production')
with app.app_context():
    try:
        # Check if admin role exists
        admin_role = Role.query.filter_by(name='Admin').first()
        if not admin_role:
            admin_role = Role(name='Admin')
            db.session.add(admin_role)
            db.session.commit()
            print('Admin role created')
        
        # Check if admin user exists
        existing_user = User.query.filter_by(email='%EMAIL%').first()
        if existing_user:
            print('Admin user already exists!')
            print('   Email:', existing_user.email)
            print('   Username:', existing_user.username)
        else:
            # Create admin user using password setter
            admin_user = User(
                email='%EMAIL%',
                username='%USERNAME%',
                is_active=True,
                role_id=admin_role.id
            )
            admin_user.password = '%PASSWORD%'  # This will use the password setter
            db.session.add(admin_user)
            db.session.commit()
            print('Admin user created successfully!')
            print('   Email: %EMAIL%')
            print('   Username: %USERNAME%')
            print('   Password: %PASSWORD%')
            print('')
            print('You can now log in at: https://your-site-render-url.com/auth/login')
            
    except Exception as e:
        print('Error creating admin user:', str(e))
        db.session.rollback()
        exit(1)
"

echo.
echo === Admin User Creation Complete ===
pause
