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
        print(parameters)
        with db.engine.begin() as connection:
            connection.execute(sqlalchemy.text(
                """
                INSERT INTO
                    barrel_ledger (transaction_type, transaction_id, red, green, blue, dark)
                VALUES
                    ('barrels purchased', :order_id, :red, :green, :blue, :dark);
                
                INSERT INTO
                    gold_ledger (transaction_type, transaction_id, gold)
                VALUES
                    ('barrel', :order_id, :cost);
                """
            ), parameters)
    except IntegrityError as e:
        print("Error:", e)
        print("Order Already Exists")
    
    return "OK"

# Gets called once a day
@router.post("/plan")
def get_wholesale_purchase_plan(wholesale_catalog: list[Barrel]):
    """ """
    print(f"Catalog: {wholesale_catalog}\n")
    try:
        with db.engine.begin() as connection:
            # current_ml is an array of the total of each barrel type
            # i.e [red, green, blue, dark]
            purchase_stats = connection.execute(sqlalchemy.text(
                """
                SELECT 
                    gold, current_ml, max_ml
                FROM barrel_purchase_stats
                """)).one()
            
    except Exception:
        print("Error fetching purchase_stats!")
        return []
    
    gold = purchase_stats.gold
    ml_inventory = purchase_stats.current_ml
    ml_max = purchase_stats.max_ml

    barrel_plan = fill_barrel_plan(gold, ml_inventory, ml_max, wholesale_catalog)
    print(f"Barrel Plan: {barrel_plan}\n")
    return barrel_plan

def fill_barrel_plan(gold: int, current_ml: list[int], max_ml: int, catalog: list[Barrel]):
    '''
    '''
    with db.engine.begin() as connection:
        constants = connection.execute(sqlalchemy.text(
            """
            SELECT
                broke_value, budget_multiplier, min_barrel_proportion, starter_potion
            FROM
                barrel_constants
            """
        )).one()

    barrel_plan = []
    barrel_types = [[1,0,0,0], [0,1,0,0], [0,0,1,0], [0,0,0,1]]
    ml_needed_each = [max_ml/4 - ml for ml in current_ml]
    starter_potion_type = [ml/100 for ml in constants.starter_potion]
    budget = int(gold * constants.budget_multiplier)
    
    # Filters out mini barrels, sorts by potion type (r->g->b->d) then by size
    catalog = sorted(filter(lambda b: b.ml_per_barrel >= 500, catalog), key = lambda b: (b.ml_per_barrel, b.potion_type), reverse=True)

    # Early game
    if (budget < constants.broke_value and max_ml < 40_000):
        barrel = min(filter(lambda b: b.potion_type == starter_potion_type, catalog), key = lambda b: b.price)
        max_qty = budget // barrel.price
        max_qty = min(max_qty, barrel.quantity)

        if (max_qty > 0):
            barrel_plan.append(
                {
                    "sku": barrel.sku,
                    "quantity": max_qty
                }
            )
    
    # Mid game
    elif (budget >= constants.broke_value and max_ml < 40_000):
        for type, ml_needed in zip(barrel_types, ml_needed_each):
            budget_each = budget//4
            for barrel in catalog:
                if (barrel.potion_type == type):
                    max_qty = ml_needed // barrel.ml_per_barrel
                    max_qty = min(max_qty, budget_each // barrel.price, barrel.quantity)

                    if (budget_each > 0 and max_qty > 0):
                        barrel_plan.append(
                        {
                            "sku": barrel.sku,
                            "quantity": max_qty
                        })
                        ml_needed -= barrel.ml_per_barrel * max_qty
                        budget_each -= barrel.price * max_qty
    
    # Late game
    else:
        # Filter catalog into large/medium and small
        # Purchase trying to meet a propotion requirement, only buying small if necessary

        big_barrels = list(filter(lambda b:b.ml_per_barrel >= 2500, catalog))
        small_barrels = list(filter(lambda b:b.ml_per_barrel == 500, catalog))

        for type, ml_needed in zip(barrel_types, ml_needed_each):
            budget_each = budget // 4
            if (big_barrels is not None):
                for barrel in big_barrels:
                    # ml_needed / (max_ml/4) is proportion of missing inventory
                    if (barrel.potion_type == type and (ml_needed/ (max_ml/4)) > constants.min_barrel_proportion):
                        max_qty = ml_needed // barrel.ml_per_barrel
                        max_qty = min(max_qty, budget // barrel.price, barrel.quantity)

                        if (budget > 0 and max_qty > 0):
                            barrel_plan.append(
                                {
                                    "sku": barrel.sku,
                                    "quantity": max_qty
                                }
                            )
                            ml_needed -= barrel.ml_per_barrel * max_qty
                            budget_each -= barrel.price * max_qty
            elif (small_barrels is not None):
                for barrel in small_barrels:
                    # ml_needed / (max_ml/4) is proportion of missing inventory
                    if (barrel.potion_type == type and (ml_needed/ (max_ml/4)) > constants.min_barrel_proportion):
                        max_qty = ml_needed // barrel.ml_per_barrel
                        max_qty = min(max_qty, budget // barrel.price, barrel.quantity)

                        if (budget > 0 and max_qty > 0):
                            barrel_plan.append(
                                {
                                    "sku": barrel.sku,
                                    "quantity": max_qty
                                }
                            )
                            ml_needed -= barrel.ml_per_barrel * max_qty
                            budget_each -= barrel.price * max_qty

    return barrel_plan
