#!/usr/bin/env python3
from sqlmodel import create_engine, Session, SQLModel
from app.core import settings

engine = create_engine(settings.DATABASE_URL)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
        session.commit()

