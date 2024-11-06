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
            SELECT
                total_potions, total_ml, total_gold
            FROM
                inventory_stats
            """
        )).one()

    return {"number_of_potions": stats.total_potions, "ml_in_barrels": stats.total_ml, "gold": stats.total_gold}

# Gets called once a day
@router.post("/plan")
def get_capacity_plan():
    """ 
    Start with 1 capacity for 50 potions and 1 capacity for 10000 ml of potion. Each additional 
    capacity unit costs 1000 gold.
    """
    capacity_plan = {"potion_capacity": 0, "ml_capacity": 0}
    try:
        with db.engine.begin() as connection:
            stats = connection.execute(sqlalchemy.text(
                """
                SELECT
                    current_potions, current_ml, gold, potion_capacity, ml_capacity
                FROM
                    capacity_stats
                """
            )).one()

            constants = connection.execute(sqlalchemy.text(
                """
                SELECT
                    max_potion_capacity, max_ml_capacity, budget_multiplier
                FROM
                    capacity_constants
                """
            )).one()

    except Exception as e:
        print("Error getting capacity plan.")
        print(capacity_plan)
        return capacity_plan

    budget = int(stats.gold * constants.budget_multiplier)
    max_potions = min(int(budget/2000), constants.max_potion_capacity)
    max_ml = min(int(budget/2000), constants.max_ml_capacity)

    capacity_plan["potion_capacity"] = max_potions
    capacity_plan["ml_capacity"] = max_ml

    print(capacity_plan)
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
                    ('capacity', :order_id, -:cost);
            END;
            """
        ), {
            "order_id": order_id,
            "potions": capacity_purchase.potion_capacity * 50,
            "ml": capacity_purchase.ml_capacity * 10_000,
            "cost": (capacity_purchase.potion_capacity + capacity_purchase.ml_capacity)*1_000

        })

    return "OK"
