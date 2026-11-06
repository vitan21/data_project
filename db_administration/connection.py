
from sqlalchemy import create_engine, URL

def get_db_engine():
    connection_url = URL.create(
        drivername="postgresql+psycopg2",
        username="postgres",
        password="postgres",
        host="localhost",
        port=5432,
        database="music_db"
    )
    return create_engine(connection_url)