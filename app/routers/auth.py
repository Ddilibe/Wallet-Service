#!/usr/bin/env python3
from faker import Faker
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.models import User
from app.database import get_session

auth = APIRouter(prefix="/auth", tags=["auth"])
fake = Faker()

@auth.get("/google")
async def google():
    return JSONResponse({})

@auth.get("/google/callback")
async def google_callback(session=Depends(get_session)):
    new_user = User(email=fake.email(), name=fake.name())
    
    return JSONResponse({})

