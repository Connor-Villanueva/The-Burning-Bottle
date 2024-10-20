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
                current_day as (
                    SELECT day
                    FROM game_info
                ),
                day_total as (
                    SELECT co.day, sum(quantity) as total
                    FROM completed_orders co
                    JOIN current_day cd on cd.day = co.day
                    GROUP BY co.day
                ),
                potion_proportions as (
                    SELECT potion_id, ROUND(SUM(quantity)::numeric / dt.total, 2) as proportion
                    FROM completed_orders co
                    JOIN day_total dt ON co.day = dt.day
                    GROUP BY potion_id, dt.total
                )

            SELECT 
            ARRAY[red, green, blue, dark] as potion_type, catalog.quantity, COALESCE(proportion,0) as proportion
            FROM catalog
            JOIN potions ON potions.id = catalog.potion_id
            LEFT JOIN potion_proportions pp on pp.potion_id = catalog.potion_id
            ORDER BY proportion DESC
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
            SELECT red, green, blue, dark, (max_potions-current_potions), game_stage
            FROM liquids
            JOIN capacity ON 1=1
            JOIN current_potions on 1=1
            JOIN game_state on 1=1
            """
        )).fetchone()
    
    # Each element looks like (potion_type, potion_quantity, relative_probability)
    liquids = [stats[0], stats[1], stats[2], stats[3]]
        
    return potion_plan(potions, liquids, stats[4], stats[5])

"""
Note:   potions is sorted in desc order of potion proportions
        Thus allowing for higher proportions to have priority
"""
def potion_plan(potions: list[int, float], liquids: list[int], max_potions: int, game_state: int):
    potion_plan = []

    # if (game_state == 1):
    #     qty_each = max_potions//6
    #     for p in potions:
    #         qty_craftable = min([a//b for (a,b) in zip(liquids, p[0]) if b != 0])
    #         qty_craftable = min(qty_each, qty_craftable, (remaining_potions)//6) - p[1]

    #         if (qty_craftable > 0):
    #             potion_plan.append(
    #                 {
    #                     "potion_type": p[0],
    #                     "quantity": qty_craftable
    #                 }
    #             )
    #             remaining_potions -= qty_craftable
    #             liquids = [a-b*qty_craftable for (a,b) in zip(liquids, p[0])]

    if (game_state == 1 or game_state == 2):
        craftable_potions = max_potions
        for p in potions:
            qty_craftable = min([a//b for (a,b) in zip(liquids, p[0]) if b != 0])
            if p[2] > 0:
                qty_craftable = min(int(max_potions*p[2]), qty_craftable) - p[1]
                print(p[1])
                if (qty_craftable > 0 and max_potions > 0):
                    potion_plan.append(
                        {
                            "potion_type": p[0],
                            "quantity": qty_craftable
                        }
                    )
                    craftable_potions -= qty_craftable
                    liquids = [a-b*qty_craftable for (a,b) in zip(liquids, p[0])]
            else:
                qty_craftable = min(qty_craftable, craftable_potions//len([x for x in potions if x[2] == 0]))

                if (qty_craftable > 0 and max_potions > 0):
                    potion_plan.append(
                        {
                            "potion_type": p[0],
                            "quantity": qty_craftable
                        }
                    )
                    max_potions -= qty_craftable
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