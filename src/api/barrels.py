from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
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
    """ """
    print(f"barrels delievered: {barrels_delivered} order_id: {order_id}")
    
    with db.engine.begin() as connection:
        current_ml = connection.execute(sqlalchemy.text("SELECT num_red_ml, num_green_ml, num_blue_ml, num_dark_ml FROM global_inventory")).fetchone()
        current_gold = connection.execute(sqlalchemy.text("SELECT gold FROM global_inventory")).fetchone()[0]

        #Update gold
        connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET gold = {current_gold - sum(barrel.price*barrel.quantity for barrel in barrels_delivered)}"))

        #Update ml quantities
        for barrel in barrels_delivered:
            if (barrel.potion_type == [1, 0, 0, 0]):
                connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET num_red_ml = {current_ml[0] + barrel.ml_per_barrel*barrel.quantity}"))
            elif (barrel.potion_type == [0, 1, 0, 0]):
                connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET num_green_ml = {current_ml[1] + barrel.ml_per_barrel*barrel.quantity}"))
            elif (barrel.potion_type == [0, 0, 1, 0]):
                connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET num_blue_ml = {current_ml[2] + barrel.ml_per_barrel*barrel.quantity}"))
            else:
                connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET num_dark_ml = {current_ml[3] + barrel.ml_per_barrel*barrel.quantity}"))
        
    return "OK"

# Gets called once a day
@router.post("/plan")
def get_wholesale_purchase_plan(wholesale_catalog: list[Barrel]):
    """ """
    print(wholesale_catalog)

    purchase_plan = []

    with db.engine.begin() as connection:
        ml_inventory = sum(connection.execute(sqlalchemy.text("SELECT num_red_ml, num_green_ml, num_blue_ml FROM global_inventory")).fetchone())
        ml_max = connection.execute(sqlalchemy.text("SELECT max_ml FROM global_inventory")).fetchone()[0]
        budget = int(1 * connection.execute(sqlalchemy.text("SELECT gold FROM global_inventory")).fetchone()[0])

    #Only concerned with selling red, blue, and green potions
    #Limit purchasing only to Small Barrels
    barrel_catalog = sorted(list(filter(lambda b: b.ml_per_barrel == 500, wholesale_catalog)), key = lambda b: b.potion_type, reverse = True)

    #Minimum number of each barrel that can be purchased considering budget and max inventory
    min_qty_budget = budget // sum(barrel.price for barrel in barrel_catalog)
    min_qty_ml = (ml_max-ml_inventory) // sum(barrel.ml_per_barrel for barrel in barrel_catalog)

    qty_each = min(min_qty_budget, min_qty_ml)

    if (qty_each == 0):
        cheapest_barrel = min(barrel_catalog, key = lambda b: b.price)
        if (cheapest_barrel.price <= budget):
            purchase_plan.append(
                {
                    "sku": cheapest_barrel.sku,
                    "quantity": 1
                }
            )
    else:
        total_cost = 0
        for barrel in barrel_catalog:
            max_affordable_qty = budget // barrel.price
            
            qty_to_purchase = min(qty_each, max_affordable_qty)

            if (qty_to_purchase > 0):
                if (barrel.quantity < qty_to_purchase):
                    qty_to_purchase = barrel.quantity
                
                cost = qty_to_purchase * barrel.price
                if (total_cost + cost <= budget):
                    purchase_plan.append(
                        {
                            "sku": barrel.sku,
                            "quantity": qty_to_purchase
                        }
                    )
                    total_cost += cost
                    budget -= cost
                else:
                    #Exceeded budget, purchase minimum
                    qty_to_purchase = budget // barrel.price
                    if qty_to_purchase > 0:
                        cost = qty_to_purchase * barrel.price
                        purchase_plan.append(
                            {
                                "sku": barrel.sku,
                                "quantity": qty_to_purchase
                            }
                        )
                        total_cost += cost
                        budget -= cost
    return purchase_plan

