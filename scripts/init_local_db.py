from app import models  # registers all SQLAlchemy models
from app.db import init_db

init_db()

print("Database tables created successfully.")
