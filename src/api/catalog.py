from fastapi import APIRouter
import sqlalchemy
from src import database as db

router = APIRouter()


@router.get("/catalog/", tags=["catalog"])
def get_catalog():
    """
    Each unique item combination must have only a single price.
    """

    catalog = []

    with db.engine.begin() as connection:
        num_green_potions = connection.execute(sqlalchemy.text("SELECT num_green_potions FROM global_inventory")).fetchone()[0]
    
    if (num_green_potions > 0):
        catalog.append(
            {
                "sku": "green_potion_0",
                "name": "green_potion",
                "quantity": num_green_potions,
                "price": 25,
                "potion_type": [0, 100, 0, 0]
            }
        )


    return catalog
