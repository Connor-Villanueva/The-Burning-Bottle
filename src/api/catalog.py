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
                SELECT potions.sku, potions.name, sum(potion_ledger.quantity) as quantity, potions.price, potion_plan.potion_type
                FROM potions
                LEFT JOIN potion_ledger ON potions.id = potion_ledger.potion_id
                LEFT JOIN potion_plan ON potions.sku = potion_plan.sku
                GROUP BY potions.sku, potions.name, potions.price, potion_plan.potion_type
                HAVING sum(potion_ledger.quantity) > 0
                LIMIT 6
                """
            ))
            time_stats = connection.execute(sqlalchemy.text(
                """
                SELECT id, hour
                FROM game_info
                ORDER BY id DESC
                LIMIT 1
                """
            )).one()

        potions_to_update = []
        if (time_stats.hour >= 20 or time_stats.hour == 0):
            for potion in potions:
                catalog.append(
                    {
                        "sku": potion.sku,
                        "name": potion.name,
                        "quantity": potion.quantity,
                        "price": 1,
                        "potion_type": potion.potion_type
                    }
                )
                potions_to_update.append(
                    {
                        "sku": potion.sku,
                        "price": 1
                    }
                )
        # Change 50 to an adjustable constant please
        else:
            for potion in potions:
                price = int((1+potion.weight) * 50)
                catalog.append(
                    {
                        "sku": potion.sku,
                        "name": potion.name,
                        "quantity": potion.quantity,
                        "price": price,
                        "potion_type": potion.potion_type
                    }
                )
                potions_to_update.append(
                    {
                        "potion_sku": potion.sku,
                        "price": price
                    }
                )
        
    except Exception:
        print("Error occured while fetching data.")
    
    print(catalog)
    return catalog

def update_prices(potions: list):
    with db.engine.begin() as connection:
        connection.execute(sqlalchemy.text(
            """
            UPDATE
                potions
            SET
                price = :price
            WHERE id = :potion_id
            """
        ), tuple(potions))
