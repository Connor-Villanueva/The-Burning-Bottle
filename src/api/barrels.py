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
    

    ml_total = get_total_ml(barrels_delivered)

    with db.engine.begin() as connection:
        connection.execute(sqlalchemy.text(
            "INSERT INTO barrel_ledger (red_ml, green_ml, blue_ml, dark_ml) VALUES (:red, :green, :blue, :dark)"
        ),
        {
            'red': ml_total[0],
            'green': ml_total[1],
            'blue': ml_total[2],
            'dark': ml_total[3]
        })
    
    return "OK"

# Calculates total ml delivers of each color
def get_total_ml(barrels: list[Barrel]):
    total_ml = [0, 0, 0, 0]

    for barrel in barrels:
        potion_type = barrel.potion_type.index(max(barrel.potion_type))
        total_ml[potion_type] = barrel.ml_per_barrel * barrel.quantity

    return total_ml

# Gets called once a day
@router.post("/plan")
def get_wholesale_purchase_plan(wholesale_catalog: list[Barrel]):
    """ """
    #print(wholesale_catalog)

    purchase_plan = []

    with db.engine.begin() as connection:
        ml_inventory = connection.execute(sqlalchemy.text("SELECT num_red_ml, num_green_ml, num_blue_ml, num_dark_ml FROM global_inventory")).fetchone()
        ml_max = connection.execute(sqlalchemy.text("SELECT max_ml FROM global_inventory")).fetchone()[0]
        budget = int(1 * connection.execute(sqlalchemy.text("SELECT gold FROM global_inventory")).fetchone()[0])

    #Sorts barrel catalog by potion_type (r -> g -> b -> d) and by decreasing size
    barrel_catalog = sorted(filter(lambda b: b.ml_per_barrel > 250, wholesale_catalog), key = lambda b: (b.potion_type, b.ml_per_barrel), reverse=True)
    print(barrel_catalog)
    barrel_types = [ [1,0,0,0] , [0,1,0,0] , [0, 0, 1, 0], [0, 0, 0, 1]]
    ml_needed_each = [ml_max//4 - x for x in ml_inventory]

    if (budget >= 400):
        for x in zip(barrel_types, ml_needed_each):
            max_budget = budget // 4
            ml = x[1]
            for barrel in barrel_catalog:
                if barrel.potion_type == x[0] and ml > 0:
                    max_qty = ml//barrel.ml_per_barrel

                    max_qty = min(max_qty, max_budget//barrel.price, barrel.quantity)
                    
                    if (max_budget > 0 and max_qty > 0):
                        purchase_plan.append(
                            {
                                "sku": barrel.sku,
                                "quantity": max_qty
                            }
                        )
                        max_budget -= barrel.price * max_qty
                        ml -= max_qty * barrel.ml_per_barrel
    else:
        min_barrel = min(filter(lambda b: b.ml_per_barrel == 500, barrel_catalog), key = lambda b: b.price)
        
        if (min_barrel.price <= budget):
            purchase_plan.append(
                {
                    "sku": min_barrel.sku,
                    "quantity": budget // min_barrel.price
                }
            )

    


    return purchase_plan

