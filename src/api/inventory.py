from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth
import math
import sqlalchemy
from src import database as db

router = APIRouter(
    prefix="/inventory",
    tags=["inventory"],
    dependencies=[Depends(auth.get_api_key)],
)

@router.get("/audit")
def get_inventory():
    """ """
        
    with db.engine.begin() as connection:
        total_ml = connection.execute(sqlalchemy.text("SELECT SUM(num_red_ml + num_green_ml + num_blue_ml + num_dark_ml) FROM global_inventory")).scalar()
        total_potions = connection.execute(sqlalchemy.text("SELECT SUM(potion_quantity) FROM potion_inventory")).scalar()
        gold = connection.execute(sqlalchemy.text("SELECT gold FROM global_inventory")).scalar()

    return {"number_of_potions": total_potions, "ml_in_barrels": total_ml, "gold": gold}

# Gets called once a day
@router.post("/plan")
def get_capacity_plan():
    """ 
    Start with 1 capacity for 50 potions and 1 capacity for 10000 ml of potion. Each additional 
    capacity unit costs 1000 gold.
    """

    with db.engine.begin() as connection:
        inventory = connection.execute(sqlalchemy.text(
            "SELECT gold, max_potions, max_ml, SUM(num_red_ml + num_green_ml + num_blue_ml + num_dark_ml) FROM global_inventory GROUP BY gold, max_potions, max_ml"
        )).fetchone()
        potions_inventory = connection.execute(sqlalchemy.text(
            "SELECT SUM(potion_quantity) FROM potion_inventory"
        )).fetchone()[0]

    if ((inventory[3]/inventory[2] > 0.5 or potions_inventory/inventory[1] > 0.5) and inventory[0] > 3000):
        return {
            "potion_capacity": 1,
            "ml_capacity": 1
        }

    return {
        "potion_capacity": 0,
        "ml_capacity": 0
        }

class CapacityPurchase(BaseModel):
    potion_capacity: int
    ml_capacity: int

# Gets called once a day
@router.post("/deliver/{order_id}")
def deliver_capacity_plan(capacity_purchase : CapacityPurchase, order_id: int):
    """ 
    Start with 1 capacity for 50 potions and 1 capacity for 10000 ml of potion. Each additional 
    capacity unit costs 1000 gold.
    """
    with db.engine.begin() as connection:
        current_plan = connection.execute(sqlalchemy.text(
            "UPDATE global_inventory SET max_potions = max_potions + :added_potions, max_ml = max_ml + :added_ml, gold = gold - :price"),
                                          {
                                              "added_potions": capacity_purchase.potion_capacity * 50,
                                              "added_ml": capacity_purchase.ml_capacity * 10000,
                                              "price" : 2000
                                          })
    print(capacity_purchase)

    return "OK"
