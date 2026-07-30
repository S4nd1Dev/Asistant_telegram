from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Nama file database kita nantinya adalah jarvis.db
DATABASE_URL = "sqlite:///jarvis.db"

# Membuat engine database
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()