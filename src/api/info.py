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
    Also, generate catalog
    """
    print("Day: " + timestamp.day)
    print("Hour: " + str(timestamp.hour))

    with db.engine.begin() as connection:
        # Updates current time and retrieves capacity and game stage statistics
        stats = connection.execute(sqlalchemy.text(
            """
            UPDATE game_info SET day = :day, hour = :hour;
        
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
            JOIN game_status ON 1=1;

            """
        ), {'day': timestamp.day, 'hour': timestamp.hour}).fetchone()

        # Update game stage based on capacities
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

        # Generate catalog every other tick
        # In game_state 3, price according to proportion
        
        # potions formatted [potion_id, quantity, proportion]
        potions = connection.execute(sqlalchemy.text(
            """
                WITH
                    current_day AS (
                        SELECT day
                        FROM game_info
                    ),
                    daily_total AS (
                        SELECT co.day, SUM(co.quantity) as total
                        FROM completed_orders co
                        JOIN current_day AS cd ON cd.day = co.day
                        GROUP BY co.day
                    ),
                    top_relative_proportions AS (
                        SELECT co.potion_id, ROUND(SUM(co.quantity)::decimal / dt.total, 2) as proportion
                        FROM completed_orders AS co
                        JOIN daily_total AS dt ON dt.day = co.day
                        GROUP BY co.potion_id, co.day, dt.total
                        HAVING ROUND(sum(co.quantity)::decimal / dt.total,2) > 0.15
                        ORDER BY proportion DESC
                        LIMIT 6
                    ),
                    random_potions AS (
                        SELECT id as potion_id
                        FROM potions
                        WHERE id NOT IN (SELECT potion_id FROM top_relative_proportions)
                        ORDER BY random()
                        LIMIT 10
                    ),
                    potion_info AS (
                        SELECT potion_id, p.red, p.green, p.blue, p.dark, proportion
                        FROM (
                        SELECT potion_id, 1 AS PRIORITY, proportion FROM top_relative_proportions
                        UNION
                        SELECT potion_id, 2 AS PRIORITY, 0 FROM random_potions
                        ) AS combined_result
                        JOIN potions p ON p.id = combined_result.potion_id
                        GROUP BY p.red, p.green, p.blue, p.dark, combined_result.priority, potion_id, combined_result.proportion
                        ORDER BY priority ASC
                        LIMIT 6
                    ),
                    potions as (
                    SELECT potion_info.potion_id, COALESCE(SUM(quantity),0) as quantity, proportion
                    FROM potion_info
                    LEFT JOIN potion_ledger ON potion_info.potion_id = potion_ledger.potion_id
                    GROUP BY potion_info.potion_id, proportion
                    ORDER BY proportion DESC, quantity DESC
                    )
                SELECT * from potions
            """
        )).fetchall()
        if (timestamp.hour % 4 == 0):
            if (stats[1] == 1):
                price = 32
                parameters = [{"potion_id": a[0], "quantity": a[1], "price": price} for a in potions]
            elif (stats[1] == 2):
                price = 22
                parameters = [{"potion_id": a[0], "quantity": a[1], "price": price} for a in potions]
            else:
                price = [int(15*(1+p[2])) if p[2] > 0.3 else int(15*(1-p[2])) for p in potions]
                parameters = [{"potion_id": a[0], "quantity": a[1], "price": b} for (a,b) in zip(potions, price)]
            
            #Reset Catalog and Insert Updated Catalog
            connection.execute(sqlalchemy.text("DELETE FROM catalog"))
            connection.execute(sqlalchemy.text(
                """
                    INSERT INTO catalog
                    (potion_id, quantity, price)
                    VALUES
                    (:potion_id, :quantity, :price);
                """
            ), parameters)

    return "OK"

