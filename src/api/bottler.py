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
    barrel_parameters = ml_cost.update({"order_id": order_id})
    try:
        with db.engine.begin() as connection:
            # Good to go
            connection.execute(sqlalchemy.text(
                """
                INSERT INTO
                    barrel_ledger (id, transaction_type, red, green, blue, dark)
                VALUES
                    ('Potions Bottled', :red, :green, :blue, :dark)
                """
            ), barrel_parameters)

            # Insert potions into potion_ledger
            # I hate this, but its fine for now
            for p in potions_delivered:
                connection.execute(sqlalchemy.text(
                    """
                    INSERT INTO
                        potion_ledger (id, transaction_type, potion_id, quantity)
                    VALUES
                        (:order_id,
                        'Potions Bottled',
                        (SELECT id FROM potions WHERE ARRAY[red,green,blue,dark] = :potion_type),
                        :quantity)
                    """
                ), 
                {
                    "potion_type": p.potion_type,
                    "quantity": p.quantity,
                    "order_id": order_id
                })
    except IntegrityError:
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
                FROM potion_purchase_stats
                """
            )).mappings().fetchall()

            # Get top selling potions based on order data
            top_potions = connection.execute(sqlalchemy.text(
                """
                """
            ))

        current_ml = stats["ml"]
        max_potions = stats["max_potions"]
        current_potions = stats["current_potions"]
        potion_plan = flood_fill_potions(top_potions, max_potions-current_potions, current_ml)
    except Exception:
        print("Error occured while fetching data")
    
    print(f"Potion Plan: {potion_plan}")
    return potion_plan

def flood_fill_potions(potions, capacity, ml):
    '''
    potions = [potion_id, potion_type, weight]
    capacity = max_potions - current_sum_potions
    ml = [red, green, blue, dark]

    Only bottle top selling potions according
    Attempt to bottle according to weight 
    '''

    total_weight = sum(p[2] for p in potions)
    bottle_plan = []
    remaning_capacity = capacity

    for potion in potions:
        proportion = potion[2] / total_weight
        
        max_potions_ml = min([b//p for (b,p) in zip(ml, potion[1])])
        max_potions_weight = int(capacity * proportion)
        assigned_quantity = min(max_potions_ml, max_potions_weight, remaning_capacity)
        
        bottle_plan.append({
            "potion_type": potion[1],
            "quantity": assigned_quantity
        })
        remaning_capacity -= assigned_quantity
        ml = [b-p*assigned_quantity for (b,p) in zip(ml, potion[1])]

        if (remaning_capacity <= 0):
            break
    return bottle_plan

if __name__ == "__main__":
    print(get_bottle_plan())
