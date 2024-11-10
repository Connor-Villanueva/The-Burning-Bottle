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
    try:
        with db.engine.begin() as connection:
            potions = connection.execute(sqlalchemy.text(
                """
                SELECT
                    sku, name, potion_type, quantity, price
                FROM
                    potential_catalog
                """
            ))

        for potion in potions:
            catalog.append(
                {
                    "sku": potion.sku,
                    "name": potion.name,
                    "quantity": potion.quantity,
                    "price": potion.price,
                    "potion_type": potion.potion_type
                }
            )

    except Exception as e:
        print("Error:", e)
    
    print(catalog)
    return catalog
