from fastapi import APIRouter, Depends
from enum import Enum
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from sqlalchemy.exc import IntegrityError
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
    """
    Inserts into potion ledger each potion and their quantity
    Inserts into barrel ledger the cost to make the potions 
    """
    print(f"potions delievered: {potions_delivered} order_id: {order_id}")
    ml_cost = {
        "red": 0,
        "green": 0,
        "blue": 0,
        "dark": 0
    }
    
    for p in potions_delivered:
        for key, value in zip(ml_cost.keys(), p.potion_type):
            ml_cost[key] += -1*value*p.quantity
    barrel_parameters = ml_cost
    barrel_parameters.update({"order_id": order_id})

    try:
        with db.engine.begin() as connection:
            # Good to go
            connection.execute(sqlalchemy.text(
                """
                INSERT INTO
                    barrel_ledger (transaction_type, transaction_id, red, green, blue, dark)
                VALUES
                    ('potions bottled', :order_id, :red, :green, :blue, :dark);
                """
            ), barrel_parameters)

            # Insert potions into potion_ledger
            # I hate this, but its fine for now
            for p in potions_delivered:
                connection.execute(sqlalchemy.text(
                    """
                    INSERT INTO
                        potion_ledger (transaction_type, transaction_id, potion_sku, quantity)
                    (SELECT
                        'bottled', :order_id, sku, :quantity
                    FROM
                        potions
                    WHERE
                        ARRAY[red, green, blue, dark] = :potion_type);
                    """
                ), 
                {
                    "potion_type": p.potion_type,
                    "quantity": p.quantity,
                    "order_id": order_id
                })
    except IntegrityError as e:
        print("Error:", e)
        print("Order already delivered")
    
    return "OK"

@router.post("/plan")
def get_bottle_plan():
    """
    Go from barrel to bottle.
    """

    potion_plan = []
    try:
        with db.engine.begin() as connection:
            stats = connection.execute(sqlalchemy.text(
                """
                SELECT ml, max_potions, current_potions
                FROM potion_plan_stats
                """
            )).one()

            # Get top selling potions based on order data
            top_potions = connection.execute(sqlalchemy.text(
                """
                SELECT sku, name, potion_type, weight
                FROM potion_plan
                """
            ))

            starter_potion = connection.execute(sqlalchemy.text(
                """
                SELECT starter_potion
                FROM barrel_constants
                """
            )).one()
            
        current_ml = stats.ml
        max_potions = stats.max_potions
        current_potions = stats.current_potions
        top_potions = [p._asdict() for p in top_potions]
        print(top_potions)
        potion_plan = flood_fill_potions(top_potions, starter_potion.starter_potion, max_potions-current_potions, current_ml)


    except Exception:
        print("Error occured while fetching data")
    
    print(f"Potion Plan: {potion_plan}")
    return potion_plan

def flood_fill_potions(potions, starter_potion, capacity, ml):
    '''
    potions = {potion_sku, potion_name, potion_type, weight}
    capacity = max_potions - current_sum_potions
    ml = [red, green, blue, dark]

    Only bottle top selling potions according
    Attempt to bottle according to weight 
    '''
    bottle_plan = []

    total_weight = sum(p['weight']for p in potions)
    remaning_capacity = capacity
    if (total_weight > 0):
        for potion in potions:
            proportion = potion['weight']/ total_weight
            
            max_potions_ml = min([b//p for (b,p) in zip(ml, potion['potion_type']) if not p == 0])
            max_potions_weight = int(capacity * proportion) if int(capacity * proportion) > 0 else 5
            assigned_quantity = min(max_potions_ml, max_potions_weight, remaning_capacity)
            
            print(f"Trying to assign: {assigned_quantity}")
            if (assigned_quantity > 0):
                bottle_plan.append({
                    "potion_type": potion['potion_type'],
                    "quantity": assigned_quantity
                })
            ml = [b-p*assigned_quantity for (b,p) in zip(ml, potion['potion_type'])]

            if (remaning_capacity <= 0):
                break
    
    # If we make it here, and the bottle plan is empty then either:
    # 1. Capacity is full
    # 2. Start of the game
    if (not bottle_plan):
        print("bottle plan was empty")
        max_potions_ml = min([b//p for (b,p) in zip(ml, starter_potion) if not p == 0])
        assigned_quantity = min(max_potions_ml, remaning_capacity)

        if (assigned_quantity > 0):
            bottle_plan.append({
                "potion_type": starter_potion,
                "quantity": assigned_quantity
            })
        
    return bottle_plan

if __name__ == "__main__":
    print(get_bottle_plan())
