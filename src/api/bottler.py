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

    # Initial logic: bottle all barrels into green potions.

    with db.engine.begin() as connection:
        max_num_potions = connection.execute(sqlalchemy.text("SELECT max_potions FROM global_inventory")).fetchone()[0]

        #[r, g, b, d]
        current_potions = [p[0] for p in list(sorted(connection.execute(sqlalchemy.text(
            "SELECT potion_quantity, potion_type FROM potion_inventory"
        )).fetchall(), key = lambda p: p[1], reverse=True))]
        current_ml = connection.execute(sqlalchemy.text("SELECT num_red_ml, num_green_ml, num_blue_ml, num_dark_ml FROM global_inventory")).fetchone()


        

    #Simple logic for now while only selling 3 types of potions
    qty_each = max_num_potions // 4
    potion_types = [[100, 0, 0, 0], [0, 100, 0, 0], [0, 0, 100, 0], [0, 0, 0, 100]]

    qty_needed_potions = [qty_each - p for p in current_potions]

    for x in zip(qty_needed_potions, current_ml, potion_types):
        max_bottles = x[1] // 100
        
        #There are cases where there are enough ml to make potions, but dont want to
        #In this case, qty_needed < 0
        #Check if qty_needed > 0 before appending
        
        if (max_bottles >= x[0] and x[0] > 0):
            bottle_plan.append(
                {
                    "potion_type": x[2],
                    "quantity": x[0]
                }
            )
        elif (max_bottles > 0 and x[0] > 0):
            bottle_plan.append(
                {
                    "potion_type": x[2],
                    "quantity": max_bottles
                }
            )

    return bottle_plan

if __name__ == "__main__":
    print(get_bottle_plan())