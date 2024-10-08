from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(auth.get_api_key)],
)

@router.post("/reset")
def reset():
    """
    Reset the game state. Gold goes to 100, all potions are removed from
    inventory, and all barrels are removed from inventory. Carts are all reset.
    """

    with db.engine.begin() as connection:
        connection.execute(sqlalchemy.text(
            "UPDATE global_inventory SET gold = 100, max_potions = 50, max_ml = 10000, num_red_ml = 0, num_green_ml = 0, num_blue_ml = 0, num_dark_ml = 0"
        ))

        connection.execute(sqlalchemy.text(
            "UPDATE potion_inventory SET potion_quantity = 0"
        ))
        connection.execute(sqlalchemy.text(
            "DELETE FROM customers"
        ))
        connection.execute(sqlalchemy.text(
            "DELETE FROM customer_cart"
        ))
        connection.execute(sqlalchemy.text(
            "UPDATE time_info SET latest_day = DEFAULT, latest_hour = DEFAULT"
        ))
    return "OK"

