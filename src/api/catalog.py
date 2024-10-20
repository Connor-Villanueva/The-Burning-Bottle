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
        # Retrieves potion information from Catalog table
        potions = connection.execute(sqlalchemy.text(
            """
            SELECT 
            sku, name, catalog.quantity, catalog.price, ARRAY[red, green, blue, dark] as potion_type
            FROM catalog
            JOIN potions ON potions.id = catalog.potion_id
            """
        )).fetchall()
        
    for potion in potions:
        if (potion[2] > 0):
            catalog.append(
                    {
                        "sku": potion[0],
                        "name": potion[1],
                        "quantity": potion[2],
                        "price": potion[3],
                        "potion_type": potion[4]
                    }
                )

    return catalog
