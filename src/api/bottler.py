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
        max_qty_day = connection.execute(sqlalchemy.text(
            "SELECT max_potions, latest_day FROM global_inventory JOIN time_info ON global_inventory.id = time_info.id ")).fetchone()
        ml_liquid = connection.execute(sqlalchemy.text(
            "SELECT num_red_ml, num_green_ml, num_blue_ml FROM global_inventory"
        )).fetchone()
        current_qty = connection.execute(sqlalchemy.text(
            "SELECT sum(potion_quantity) FROM potion_inventory"
        )).fetchone()[0]
        #Calculates and returns relative probabilities of top 6 potions types on a given day
        potion_distribution = connection.execute(sqlalchemy.text(
            '''
            WITH
            daily_totals as (
            SELECT day, sum(quantity) AS day_total
            FROM completed_orders
            GROUP BY day
            )
            SELECT co.potion_sku, ROUND(SUM(co.quantity)::decimal / dt.day_total, 2) as relative_potion_probability
            FROM completed_orders co
            JOIN daily_totals dt ON co.day = dt.day
            WHERE co.day = :day
            GROUP BY co.potion_sku, co.day, dt.day_total
            ORDER BY co.day
            LIMIT 6;
            '''
        ), {"day": max_qty_day[1]}).fetchall()

        #Only use potions with relative probability > 30%
        potions = connection.execute(sqlalchemy.text(
            "SELECT potion_type, potion_quantity FROM potion_inventory WHERE potion_sku IN :potion_sku"
        ), {"potion_sku": tuple(p[0] for p in potion_distribution if p[1] > 0.30)}).fetchall()

        if (len(potions) < 6):
            all_potions = connection.execute(sqlalchemy.text(
                "SELECT potion_type, potion_quantity FROM potion_inventory WHERE potion_sku NOT IN :potion_sku"
                ), {"potion_sku": tuple(p[0] for p in potion_distribution)}).fetchall()
            for _ in range(6-len(potions)):
                #Append random potions
                #Temporary: Filtering potions with dark liquid
                #
                potions.append(random.choice(tuple(filter(lambda p: p[0][3] == 0,all_potions))))
    
    qty_each = (max_qty_day[0] - current_qty) // 6
    for p in potions:
        max_potions = [a//b for (a,b) in zip(ml_liquid, p[0]) if b != 0]
        max_potions = min(qty_each, min(max_potions))

        if (p[1] < max_potions):
            bottle_plan.append(
                {
                    "potion_type": p[0],
                    "quantity": max_potions - p[1]
                }
            )
            ml_liquid = [a-b*(max_potions - p[1]) for (a,b) in zip(ml_liquid, p[0])]
    return bottle_plan

if __name__ == "__main__":
    print(get_bottle_plan())