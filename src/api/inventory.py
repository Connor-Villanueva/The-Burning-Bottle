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
        stats = connection.execute(sqlalchemy.text(
            """
            WITH
                total_potions as (
                    SELECT SUM(potion_quantity) as total_potions
                    FROM potion_inventory
                ),
                total_ml as (
                    SELECT SUM(num_red_ml + num_green_ml + num_blue_ml + num_dark_ml) as total_ml
                    FROM global_inventory
                )
            SELECT total_potions, total_ml, gold
            FROM global_inventory
            JOIN total_potions ON 1=1
            JOIN total_ml ON 1=1
            """
        )).fetchone()

    return {"number_of_potions": stats[0], "ml_in_barrels": stats[1], "gold": stats[2]}

# Gets called once a day
@router.post("/plan")
def get_capacity_plan():
    """ 
    Start with 1 capacity for 50 potions and 1 capacity for 10000 ml of potion. Each additional 
    capacity unit costs 1000 gold.
    """
    
    try:
        capacity_plan = {
        "potion_capacity": 0,
        "ml_capacity": 0
        }
        
        with db.engine.begin() as connection:
            stats = connection.execute(sqlalchemy.text(
                """
                SELECT gold, current_potions, current_ml, max_potions, max_ml
                FROM shop_stats
                """
            )).mappings().fetchone()
        
        gold = stats['gold']
        current_potions = stats['current_potions']
        current_ml = stats['current_ml']
        max_potions = stats['max_potions']
        max_ml = stats['max_ml']

        return fill_capacity_plan(gold, current_potions, current_ml, max_potions, max_ml)

    except Exception:
        print("Error")
        return {
            "potion_capacity": 0,
            "ml_capacity": 0
        }

def fill_capacity_plan(gold: int, current_potions: int, current_ml: int, max_potions: int, max_ml: int):
    '''
    Always purchase at 2:1 ratio of potion:ml -> 3000 gold
    This needs work, I dont like it
    '''
    capacity_plan = {"potion_capacity": 0, "ml_capacity": 0}
    budget = gold if gold < 30_000 else 0.1 * int(gold)

    while budget > 0:
        if ((current_potions/max_potions >= 0.8 or current_ml/max_ml >= 0.8) and budget >= 3000):
            capacity_plan["potion_capacity"] += 2
            capacity_plan["ml_capacity"] += 1
        budget -= 3_000

    return capacity_plan

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
    print(f"Capacity Purchased: {capacity_purchase}")
    
    with db.engine.begin() as connection:
        connection.execute(sqlalchemy.text(
            """
            BEGIN;
                INSERT INTO 
                    capacity_ledger
                    (id, potions, ml)
                VALUES
                    (:order_id, :potions, :ml);

                INSERT INTO
                    gold_ledger
                    (transaction_type, transaction_id, gold)
                VALUES
                    ('Capacity Purchased', :order_id, :cost);
            END;
            """
        ), {
            "order_id": order_id,
            "potions": capacity_purchase.potion_capacity * 50,
            "ml": capacity_purchase.ml_capacity * 10_000,
            "cost": -1*(capacity_purchase.potion_capacity + capacity_purchase.ml_capacity)*1_000

        })

    return "OK"
