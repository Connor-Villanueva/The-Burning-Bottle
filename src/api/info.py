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
            "UPDATE game_info SET day = :day, hour = :hour"
        ), {'day': timestamp.day, 'hour': timestamp.hour})

        stats = connection.execute(sqlalchemy.text(
            """
                WITH
                    game_status AS (
                        SELECT game_stage
                        FROM game_info
                    ),
                    liquid_capacity AS (
                        SELECT sum(liquids)
                        FROM capacity_ledger
                    )

                SELECT * FROM liquid_capacity
                JOIN game_status ON 1=1
            """
        )).fetchone()
        liquid_capacity = stats[0]
        current_stage = stats[1]
        
        if (liquid_capacity >= 40_000 and liquid_capacity < 80_000 and current_stage != 2):
            connection.execute(sqlalchemy.text(
                "UPDATE game_info SET game_stage = 2"
            ))
        elif (liquid_capacity >= 80_000 and current_stage != 3):
            connection.execute(sqlalchemy.text(
                "UPDATE game_info SET game_stage = 3"
            ))

    return "OK"

