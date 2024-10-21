from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db

import random

router = APIRouter(
    prefix="/info",
    tags=["info"],
    dependencies=[Depends(auth.get_api_key)],
)

class Timestamp(BaseModel):
    day: str
    hour: int

@router.post("/current_time")
def post_time(timestamp: Timestamp):
    """
    Share current time.

    Also, want to make decision about current game state
    """
    print("Day: " + timestamp.day)
    print("Hour: " + str(timestamp.hour))

    with db.engine.begin() as connection:
        connection.execute(sqlalchemy.text(
            "UPDATE time_info SET (latest_day, latest_hour) = (:day, :hour)"),
        {
            "day": timestamp.day,
            "hour": timestamp.hour
        })

    return "OK"

