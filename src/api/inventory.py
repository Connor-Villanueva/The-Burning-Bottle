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
    with db.engine.begin() as connection:
        #Fetch shop stats formatted [potions, liquids, gold]
        stats = connection.execute(sqlalchemy.text(
            """
            WITH
                total_gold as (
                    SELECT sum(gold) as gold
                    FROM gold_ledger
                ),
                total_potions as (
                    SELECT sum(quantity) as potions
                    FROM potion_ledger
                ),
                total_liquids as (
                    SELECT sum(red_ml+green_ml+blue_ml+dark_ml) liquids
                    FROM barrel_ledger
                ),
                current_capacity as (
                    SELECT sum(potions) as max_potions, sum(liquids) as max_liquids
                    FROM capacity_ledger
                ),
                game_status as (
                    SELECT game_stage
                    FROM game_info
                ),
                shop_stats as (
                    SELECT * FROM total_potions
                    JOIN total_liquids on 1=1
                    JOIN total_gold on 1=1
                    JOIN current_capacity on 1=1
                    JOIN game_status on 1=1
                )

            SELECT *
            FROM shop_stats
            """
        )).fetchone()

    potions = stats[0]
    liquids = stats[1]
    gold = stats[2]
    max_potions = stats[3]
    max_liquids = stats[4]
    stage = stats[5]

    print(stats)

    capacity_plan = {
        "potion_capacity": 0,
        "ml_capacity": 0
    }

    #Helper function to determine proportions
    def check_liquids(ml, max_ml):
        if (ml/max_ml > 0.5):
            return True
        return False
    def check_potions(p, max_p):
        if (p/max_p > 0.75):
            return True
        return False
    
    #Game stages 1-3 correspond to early, mid, and late game
    #Different strategies for each stage
    if (stage == 1):
        #Buy one capacity at a time
        if (check_liquids(liquids, max_liquids) and gold > 2500):
            capacity_plan["ml_capacity"] += 1
            gold -= 1000
    
    elif (stage == 2):
        #Prioritize potion capacity but can buy both
        if (check_potions(potions, max_potions) and gold > 2500):
            capacity_plan["potion_capacity"] += 1
            gold -= 1000
        if (check_liquids(liquids, max_liquids) and gold > 2500):
            capacity_plan["ml_capacity"] += 1
            gold -= 1000
    
    elif (stage == 3):
        #Buy up to 3
        if ((check_liquids(liquids, max_liquids) or check_potions(potions, max_potions)) and gold > 2500):
            max_purchaseable = min(3, gold//2000)
            capacity_plan["potion_capacity"] = max_purchaseable
            capacity_plan["ml_capacity"] = max_purchaseable

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
    print(capacity_purchase)
    with db.engine.begin() as connection:
        purchase_id = connection.execute(sqlalchemy.text(
            """
            DO $$
            BEGIN
                INSERT INTO capacity_ledger (id, potions, liquids) VALUES (:id, :potions, :liquids);
                INSERT INTO gold_ledger (transaction_type, transaction_id, gold) VALUES ('Purchase Capacity', :id, :cost);
            END $$
            """
        ), {
            'id': order_id,
            'potions': capacity_purchase.potion_capacity * 50,
            'liquids': capacity_purchase.ml_capacity * 10_000,
            'cost': (capacity_purchase.potion_capacity + capacity_purchase.ml_capacity) * -1000
        })

    return "OK"
