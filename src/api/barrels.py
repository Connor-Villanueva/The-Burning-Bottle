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

    return "OK"

# Gets called once a day
@router.post("/plan")
def get_wholesale_purchase_plan(wholesale_catalog: list[Barrel]):
    """ """
    print(wholesale_catalog)

    with db.engine.begin() as connection:
        inventory = connection.execute(sqlalchemy.text("SELECT * FROM global_inventory")).fetchall()
    
    num_green_potions = inventory[0][2]
    gold = inventory[0][4]
    if (num_green_potions < 10):
        for barrel in wholesale_catalog:
            if (barrel.sku == "SMALL_BLUE_BARREL" and barrel.price < gold):
                return [
                    {
                        "sku": "SMALL_BLUE_BARREL",
                        "quantity": 1,
                    }
                ]   
    
    return [
        {
            "sku": "SMALL_RED_BARREL",
            "quantity": 1,
        }
    ]

