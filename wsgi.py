from app import create_app

# Default to 'Config' class; can switch via APP_CONFIG env if you add more configs
app = create_app()
