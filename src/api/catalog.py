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
        day = connection.execute(sqlalchemy.text("SELECT latest_day FROM time_info")).fetchone()[0]
        #Calculates and returns relative probabilities of top 6 potions types on a given day
        potions = connection.execute(sqlalchemy.text(
            '''
            SELECT potion_sku, potion_name, potion_quantity, potion_price, potion_type
            FROM potion_inventory
            ORDER BY RANDOM()
            LIMIT 6
        '''
        ))

    for row in potions:
        catalog.append(
            {
                "sku": row.potion_sku,
                "name": row.potion_name,
                "quantity": 50,
                "price": 40,
                "potion_type": row.potion_type
            }
        )
    print(catalog)

    return catalog
