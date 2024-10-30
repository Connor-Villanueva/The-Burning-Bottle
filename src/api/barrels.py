from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from sqlalchemy.exc import IntegrityError
from src import database as db

router = APIRouter(
    prefix="/barrels",
    tags=["barrels"],
    dependencies=[Depends(auth.get_api_key)],
)

class Barrel(BaseModel):
    sku: str

    ml_per_barrel: int
    potion_type: list[int]
    price: int

    quantity: int

@router.post("/deliver/{order_id}")
def post_deliver_barrels(barrels_delivered: list[Barrel], order_id: int):
    """ 
    Calculates total ml received and total cost
    Reflects changes into barrel and gold ledgers
    """
    print(f"barrels delievered: {barrels_delivered} order_id: {order_id}")
    
    ml_received = {"red": 0, "green": 0, "blue": 0, "dark": 0}
    cost = 0
    try:
        for b in barrels_delivered:
            ml_in_barrel = [ml * b.ml_per_barrel * b.quantity for ml in b.potion_type]
            cost -= b.price * b.quantity
            for key, value in zip(ml_received, ml_in_barrel):
                ml_received[key] += value

        parameters = ml_received
        parameters.update({"cost": cost})
        parameters.update({"order_id": order_id})
        with db.engine.begin() as connection:
            connection.execute(sqlalchemy.text(
                """
                BEGIN;
                    INSERT INTO
                        barrel_ledger (id, transaction_type, red, green, blue, dark)
                    VALUES
                        (:order_id, 'Barrels Purchased', :red, :green, :blue, :dark);
                    
                    INSERT INTO
                        gold_ledger (transaction_type, transaction_id, gold)
                    VALUES
                        ('Barrels Purchased', :order_id, :cost);
                END;
                """
            ), parameters)
    except IntegrityError as e:
        print("Order Already Exists")
    
    return "OK"

# Gets called once a day
@router.post("/plan")
def get_wholesale_purchase_plan(wholesale_catalog: list[Barrel]):
    """ """
    print(wholesale_catalog)
    try:
        with db.engine.begin() as connection:
            purchase_stats = connection.execute(sqlalchemy.text(
                """
                SELECT 
                    gold, current_ml, max_ml 
                FROM barrel_purchase_stats
                """)).mappings().fetchone()
            # Put a sql query for the top potion of one color
            top_single_potion = connection.execute(sqlalchemy.text())
    except Exception:
        print("Error fetching purchase_stats!")
        return []
    
    gold = purchase_stats["gold"]
    ml_inventory = purchase_stats["current_ml"]
    ml_max = purchase_stats["max_ml"]
    top_single_potion = [color/100 for color in top_single_potion]
    
    return get_barrel_plan(gold, ml_inventory, ml_max, wholesale_catalog, top_single_potion)

def get_barrel_plan(gold: int, current_ml: list[int], max_ml: int, catalog: list[Barrel], top_potion: list[int]):
    '''
    Please future me, make this look nicer. It's literally the same logic each time...
    '''
    barrel_plan = []
    barrel_types = [[1,0,0,0], [0,1,0,0], [0,0,1,0], [0,0,0,1]]
    ml_needed_each = [max_ml/4 - ml for ml in current_ml]
    
    #Filters out mini barrels, sorts by potion type (r->g->b->d) then by size
    catalog = sorted(filter(lambda b: b.ml_per_barrel >= 500, catalog), key = lambda b: (b.ml_per_barrel, b.potion_type), reverse=True)

    if (max_ml < 40_000):
        budget = gold
        
        #If we're broke (early game) buy barrel that corresponds to best selling single color potion of the day
        if (budget < 300):
            min_barrel = min(filter(lambda b:b.ml_per_barrel == 500 and b.potion_type == top_potion, catalog), key = lambda b: b.price)
            if (min_barrel.price <= budget):
                barrel_plan.append(
                {
                    "sku": min_barrel.sku,
                    "quantity": budget // min_barrel.price
                })
        else:
            for type, ml_needed in zip(barrel_types, ml_needed_each):
                for barrel in catalog:
                    if (barrel.potion_type == type and ml_needed > 0):
                        max_qty = ml_needed // barrel.ml_per_barrel
                        max_qty = min(max_qty, budget // barrel.price, barrel.quantity)

                        if (budget > 0 and max_qty > 0):
                            barrel_plan.append(
                                {
                                    "sku": barrel.sku,
                                    "quantity": max_qty
                                }
                            )
                            ml_needed -= barrel.ml_per_barrel*max_qty
                            budget -= barrel.price * max_qty
    else:
        # At this point, we want to only buy large and medium if we can
        # Only buy small if absolutely necessary

        # Change 0.85 to be an adjustable constant in db
        budget = int(0.85 * float(gold))
        big_barrels = list(filter(lambda b:b.ml_per_barrel >= 2500, catalog))
        small_barrels = list(filter(lambda b:b.ml_per_barrel == 500, catalog))

        for type, ml_needed in zip(barrel_types, ml_needed_each):
            # Change 0.2 to be an adjustable constant in db
            print("---------New iteration-----------")
            print(f"{type} | {ml_needed}")
            #print(list(big_barrels))
            if (big_barrels is not None):
                for barrel in big_barrels:
                    print(f"{barrel.sku} | {ml_needed/(max_ml)/4}")
                    if (barrel.potion_type == type and ml_needed/(max_ml/4) > 0.2):
                        max_qty = ml_needed // barrel.ml_per_barrel
                        print(f"{max_qty} | {budget//barrel.price} | {barrel.quantity}")
                        max_qty = min(max_qty, budget//barrel.price, barrel.quantity)                        

                        if (budget > 0 and max_qty > 0):
                            barrel_plan.append(
                                {
                                    "sku": barrel.sku,
                                    "quantity": max_qty
                                }
                            )
                            ml_needed -= barrel.ml_per_barrel * max_qty
                            budget -= barrel.price * max_qty
                    print()
            elif (small_barrels is not None):
                for barrel in small_barrels:
                    if (barrel.potion_type == type):
                        max_qty = ml_needed // barrel.ml_per_barrel
                        max_qty = min(max_qty, budget//barrel.price, barrel.quantity)

                        if (budget > 0 and max_qty > 0):
                            barrel_plan.append(
                                {
                                    "sku": barrel.sku,
                                    "quantity": max_qty
                                }
                            )
                            ml_needed -= barrel.ml_per_barrel * max_qty
                            budget -= barrel.price * max_qty        
    return barrel_plan
