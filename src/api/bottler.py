from fastapi import APIRouter, Depends
from enum import Enum
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db

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

    num_green_potions = 0
    num_green_ml = 0
    for potion in potions_delivered:
        if (potion.potion_type == [0, 100, 0, 0]):
            num_green_potions += potion.quantity
            num_green_ml -= 100 * potion.quantity

    with db.engine.begin() as connection:
        num_green_potions += connection.execute(sqlalchemy.text("SELECT num_green_potions FROM global_inventory")).fetchone()[0]
        num_green_ml += connection.execute(sqlalchemy.text("SELECT num_green_ml FROM global_inventory")).fetchone()[0]
        
        connection.execute(sqlalchemy.text("UPDATE global_inventory SET num_green_potions = " + str(num_green_potions)))
        connection.execute(sqlalchemy.text("UPDATE global_inventory SET num_green_ml = " + str(num_green_ml)))
        
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

    # Initial logic: bottle all barrels into green potions.

    with db.engine.begin() as connection:
        num_green_ml = connection.execute(sqlalchemy.text("SELECT num_green_ml FROM global_inventory")).fetchone()[0]
    
    if (num_green_ml >= 100):
        num_green_potions = 0
        while (num_green_ml % 100 == 0 and num_green_ml > 0) :
            num_green_potions += 1
            num_green_ml -= 100
        
        bottle_plan.append(
            {
                "potion_type": [0, 100, 0, 0],
                "quantity": num_green_potions
            }
        )


    return bottle_plan

if __name__ == "__main__":
    print(get_bottle_plan())