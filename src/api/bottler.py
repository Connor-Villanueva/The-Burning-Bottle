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
    # print(f"potions delievered: {potions_delivered} order_id: {order_id}")

    # Formatted [red, green, blue, dark]
    ml_used = [0, 0, 0, 0]
    for potion in potions_delivered:
        ml_used = [a-b*potion.quantity for (a,b) in zip(ml_used, potion.potion_type)]

    potions = [{'potion_type': p.potion_type, 'quantity':p.quantity} for p in potions_delivered]
    
    with db.engine.begin() as connection:
        connection.execute(sqlalchemy.text(
            """
                INSERT INTO potion_ledger
                (potion_id, quantity)
                SELECT id, :quantity
                FROM potions
                WHERE ARRAY[red, green, blue, dark] = :potion_type;
            """
        ), potions)
        connection.execute(sqlalchemy.text(
            "INSERT INTO barrel_ledger (red_ml, green_ml, blue_ml, dark_ml) VALUES (:red, :green, :blue, :dark)"
        ), {"red": ml_used[0], "green": ml_used[1], "blue": ml_used[2], "dark": ml_used[3]})

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
        # potions formatted as [red, green, blue, dark, quantity, proportion]
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
                    )
                SELECT red, green, blue, dark, COALESCE(SUM(quantity),0) as quantity, proportion
                FROM potion_info
                LEFT JOIN potion_ledger ON potion_info.potion_id = potion_ledger.potion_id
                GROUP BY potion_info.potion_id, red, green, blue, dark, proportion
                ORDER BY proportion DESC, quantity DESC
            """
        )).fetchall()
        
        # current inventory stats as [red, green, blue, dark, max_craftable_potions, game_state]
        stats = connection.execute(sqlalchemy.text(
            """
            WITH
                liquids as (
                    SELECT sum(red_ml) as red, sum(green_ml) as green, sum(blue_ml) as blue, sum(dark_ml) as dark
                    FROM barrel_ledger
                ),
                capacity as (
                    SELECT sum(potions) as max_potions
                    FROM capacity_ledger
                ),
                current_potions as (
                    SELECT sum(quantity) as current_potions
                    FROM potion_ledger
                    WHERE quantity IS NOT null
                ),
                game_state as (
                select game_stage
                FROM game_info
                )
            SELECT red, green, blue, dark, (max_potions - current_potions) as max_capacity, game_stage
            FROM liquids
            JOIN capacity ON 1=1
            JOIN current_potions on 1=1
            JOIN game_state on 1=1
            """
        )).fetchone()
    
    # Each element looks like (potion_type, potion_quantity, relative_probability)
    potions = [([p[0], p[1], p[2], p[3]], p[4], p[5]) for p in potions]
    liquids = [stats[0], stats[1], stats[2], stats[3]]
        
    return potion_plan(potions, liquids, stats[4], stats[5])

"""
Note:   potions is sorted in desc order of potion proportions
        Thus allowing for higher proportions to have priority
"""
def potion_plan(potions: list[int, float], liquids: list[int], max_potions: int, game_state: int):
    potion_plan = []
    
    if (game_state == 1):
        qty_each = max_potions//6

        for p in potions:
            qty_craftable = min([a//b for (a,b) in zip(liquids, p[0]) if b != 0])
            qty_craftable = min(qty_each, qty_craftable) - p[1]

            if (qty_craftable > 0):
                potion_plan.append(
                    {
                        "potion_type": p[0],
                        "quantity": qty_craftable
                    }
                )
                liquids = [a-b*qty_craftable for (a,b) in zip(liquids, p[0])]

    elif (game_state == 2):
        for p in potions:
            qty_craftable = min([a//b for (a,b) in zip(liquids, p[0]) if b != 0])
            if p[2] > 0:
                qty_craftable = min(int(max_potions*p[2]), qty_craftable) - p[1]

                if (qty_craftable > 0):
                    potion_plan.append(
                        {
                            "potion_type": p[0],
                            "quantity": qty_craftable
                        }
                    )
                    max_potions -= qty_craftable
                    liquids = [a-b*qty_craftable for (a,b) in zip(liquids, p[0])]
            else:
                qty_craftable = min(qty_craftable, max_potions//len([x for x in potions if x[2] == 0]))

                if (qty_craftable > 0):
                    potion_plan.append(
                        {
                            "potion_type": p[0],
                            "quantity": qty_craftable
                        }
                    )
                    liquids = [a-b*qty_craftable for (a,b) in zip(liquids, p[0])]
    elif (game_state == 3):
        potions = [p for p in potions if p[2] != 0]

        for p in potions:
            qty_craftable = min([a//b for (a,b) in zip(liquids, p[0]) if b != 0])
            qty_craftable = min(int(max_potions*p[2]), qty_craftable) - p[1]

            if (qty_craftable > 0):
                potion_plan.append(
                    {
                        "potion_type": p[0],
                        "quantity": qty_craftable
                    }
                )
                liquids = [a-b*qty_craftable for (a,b) in zip(liquids, p[0])]

    return potion_plan

if __name__ == "__main__":
    print(get_bottle_plan())