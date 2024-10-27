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

    
 
    return bottle_plan

def flood_fill_potions(potions, capacity):
    '''
    potions = [potion_sku, potion_type, weight]
    capacity = [max_potions - current_sum_potions]
    Performs flood fill algorithm to determine potion bottling
    '''

    total_weight = sum(p[2] for p in potions)
    bottle_plan = []
    remaning_capacity = capacity

    for potion in potions:
        proportion = potion[2] / total_weight

        assigned_quantity = int(proportion*capacity)
        if (assigned_quantity > remaning_capacity):
            assigned_quantity = remaning_capacity
        
        bottle_plan.append({
            "potion_type": potion[1],
            "quantity": assigned_quantity
        })
        remaning_capacity -= assigned_quantity

        if (remaning_capacity <= 0):
            break
    return bottle_plan

if __name__ == "__main__":
    print(get_bottle_plan())
