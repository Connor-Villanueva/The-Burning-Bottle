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
        #Update gold
        connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET gold = gold - :cost"),
                           {
                               "cost": sum(barrel.price*barrel.quantity for barrel in barrels_delivered)
                           })

        #Update ml quantities
        for barrel in barrels_delivered:
            if (barrel.potion_type == [1, 0, 0, 0]):
                connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET num_red_ml = num_red_ml + :num_red_ml"), 
                                   {
                                       "num_red_ml": barrel.ml_per_barrel*barrel.quantity
                                   })
            elif (barrel.potion_type == [0, 1, 0, 0]):
                connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET num_green_ml = num_green_ml + :num_green_ml"), 
                                   {
                                       "num_green_ml": barrel.ml_per_barrel*barrel.quantity
                                   })
            elif (barrel.potion_type == [0, 0, 1, 0]):
                connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET num_blue_ml = num_blue_ml + :num_blue_ml"), 
                                   {
                                       "num_blue_ml": barrel.ml_per_barrel*barrel.quantity
                                   })
            else:
                connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET num_dark_ml = num_dark_ml + :num_dark_ml"), 
                                   {
                                       "num_dark_ml": barrel.ml_per_barrel*barrel.quantity
                                   })
        
    return "OK"

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

