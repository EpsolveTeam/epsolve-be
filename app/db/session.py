import os
from sqlalchemy import event
from sqlmodel import create_engine, Session
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL, 
    echo=False,           
    pool_pre_ping=True    
)

@event.listens_for(engine, "connect")
def set_search_path(dbapi_connection, connection_record):
    """
    Memastikan koneksi database diarahkan ke skema yang tepat 
    berdasarkan ENV_STATE (dev atau prod).
    """
    cursor = dbapi_connection.cursor()
    
    try:
        cursor.execute("SET search_path TO public")
    finally:
        cursor.close()

def get_session():
    """
    Generator untuk menyediakan session database ke API endpoint.
    """
    with Session(engine) as session:
        yield session