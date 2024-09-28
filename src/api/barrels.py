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
    
    num_green_ml = 0
    gold = 0
    
    
    for barrel in barrels_delivered:
        gold -= barrel.price * barrel.quantity
        if (barrel.potion_type == [0, 1, 0, 0]):
            num_green_ml += barrel.ml_per_barrel * barrel.quantity
    
    with db.engine.begin() as connection:
        num_green_ml += connection.execute(sqlalchemy.text("SELECT num_green_ml FROM global_inventory")).fetchone()[0]
        gold += connection.execute(sqlalchemy.text("SELECT gold FROM global_inventory")).fetchone()[0]
        connection.execute(sqlalchemy.text("UPDATE global_inventory SET num_green_ml = " + str(num_green_ml)))
        connection.execute(sqlalchemy.text("UPDATE global_inventory SET gold = " + str(gold)))

    return "OK"

# Gets called once a day
@router.post("/plan")
def get_wholesale_purchase_plan(wholesale_catalog: list[Barrel]):
    """ """
    print(wholesale_catalog)

    purchase_plan = []

    with db.engine.begin() as connection:
        num_green_potions = (connection.execute(sqlalchemy.text("SELECT num_green_potions FROM global_inventory")).fetchone())[0]
        gold = (connection.execute(sqlalchemy.text("SELECT gold FROM global_inventory")).fetchone())[0]

    if (num_green_potions < 10):
        for barrel in wholesale_catalog:
            if (barrel.sku == "SMALL_GREEN_BARREL" and barrel.price <= gold):
                purchase_plan.append(
                    {
                        "sku": barrel.sku,
                        "quantity": 1
                    }
                )

    #For future purchases, keeping track of gold within locally is necessay to prevent an invalid purchase plan
    
    return purchase_plan

