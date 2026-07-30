from sqlalchemy import Column, Integer, String, Text
from database.db import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, unique=True, index=True)
    ai_api_key = Column(String, nullable=True)
    google_oauth_token = Column(Text, nullable=True)