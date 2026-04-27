from app import models  # registers all SQLAlchemy models
from app.db import engine
from app.models.base import Base

Base.metadata.create_all(bind=engine)

print("Database tables created successfully.")
