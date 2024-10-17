from fastapi import APIRouter, Depends
from enum import Enum
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db
import random

router = APIRouter(
    prefix="/bottler",
    tags=["bottler"],
    dependencies=[Depends(auth.get_api_key)],
)

class PotionInventory(BaseModel):
    potion_type: list[int]
    quantity: int

@router.post("/deliver/{order_id}")
def post_deliver_bottles(potions_delivered: list[PotionInventory], order_id: int):
    """ """
    print(f"potions delievered: {potions_delivered} order_id: {order_id}")

    ml_used = [0, 0, 0, 0]  #[r, g, b, d]

    with db.engine.begin() as connection:

        for potion in potions_delivered:
            ml_used = [a+(b*potion.quantity) for a,b in zip(ml_used, potion.potion_type)]
            
            connection.execute(sqlalchemy.text(f"UPDATE potion_inventory SET potion_quantity = potion_quantity + {potion.quantity} WHERE potion_type = :potion_type"), {'potion_type': potion.potion_type})
        
        connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET num_red_ml = num_red_ml - {ml_used[0]}, num_green_ml = num_green_ml - {ml_used[1]}, num_blue_ml = num_blue_ml - {ml_used[2]}, num_dark_ml = num_dark_ml - {ml_used[3]}"))
     
    return "OK"

@router.post("/plan")
def get_bottle_plan():
    """
    Go from barrel to bottle.
    """

    bottle_plan = []

    # Each bottle has a quantity of what proportion of red, blue, and
    # green potion to add.
    # Expressed in integers from 1 to 100 that must sum up to 100.

    with db.engine.begin() as connection:
        potions = connection.execute(sqlalchemy.text(
            """
                WITH
                current_day AS (
                    SELECT latest_day as day
                    FROM time_info
                ),
                daily_total AS (
                    SELECT co.day, SUM(co.quantity) as daily_total
                    FROM completed_orders co
                    GROUP BY co.day
                ),
                top_relative_proportions AS (
                    SELECT co.potion_sku, ROUND(SUM(co.quantity)::decimal / dt.daily_total, 2) AS relative_proportion
                    FROM completed_orders co
                    JOIN daily_total dt ON co.day = dt.day
                    JOIN current_day cd ON co.day = cd.day
                    GROUP BY co.potion_sku, co.day, dt.daily_total
                    HAVING ROUND(SUM(co.quantity)::decimal / dt.daily_total, 2) > 0.15
                    ORDER BY relative_proportion DESC
                    LIMIT 6
                ),
                random_potions AS (
                    SELECT potion_sku
                    FROM potion_inventory
                    ORDER BY random()
                    LIMIT 10
                ),
                total_potions AS (
                    SELECT potion_sku, SUM(potion_quantity) AS total
                    FROM potion_inventory
                    GROUP BY potion_sku
                ),
                potion_info AS (
                    SELECT max_potions, num_red_ml AS red_ml, num_green_ml AS green_ml, num_blue_ml AS blue_ml, num_dark_ml AS dark_ml
                    FROM global_inventory
                )
                SELECT p.potion_type, p.potion_quantity, relative_proportion
                FROM (
                SELECT potion_sku, relative_proportion, 1 AS priorty FROM top_relative_proportions
                UNION
                SELECT potion_sku, 0, 2 AS priorty FROM random_potions
                ) AS combined_result
                JOIN potion_inventory p ON p.potion_sku = combined_result.potion_sku
                CROSS JOIN potion_info pi
                ORDER BY priorty ASC
                LIMIT 6
            """
        )).fetchall()

        inventory_info = connection.execute(sqlalchemy.text(
            """
                SELECT 
                max_potions, current_potions, num_red_ml, num_green_ml, num_blue_ml, num_dark_ml
                FROM global_inventory
                JOIN (
                SELECT sum(potion_quantity) as current_potions
                FROM potion_inventory
                ) AS total ON 1=1
            """
        )).fetchone()
    max_potions = inventory_info[0] - inventory_info[1]
    liquids = [inventory_info[2], inventory_info[3], inventory_info[4], inventory_info[5]]
    
    #Each element looks like (potion_type, potion_quantity, relative_probability)
    for p in potions:
        ideal_qty = 0
        max_qty = [b//a for (a,b) in zip(p[0], liquids) if a != 0]
        if (p[2] > 0):
            ideal_qty = int(max_potions*p[2])
        else:
            ideal_qty = max_potions // len(potions)
        
        max_qty = min(ideal_qty, min(max_qty))
        if (max_qty > 0):
            bottle_plan.append(
                {
                    "potion_type": p[0],
                    "quantity": max_qty
                }
            )
        liquids = [b - a*max_qty for (a,b) in zip(p[0],liquids)]
 
    return bottle_plan

if __name__ == "__main__":
    print(get_bottle_plan())