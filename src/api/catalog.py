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
        # At end of day, sell all stock that has no impact on next day
        # Implement this future me!
        if (time_stats.hour >= 20 or time_stats.hour == 0):
            for potion in potions:
                catalog.append(
                    {
                        "sku": potion["sku"],
                        "name": potion["name"],
                        "quantity": potion["quantity"],
                        "price": 1,
                        "potion_type": potion["potion_type"]
                    }
                )
        # Change 35 to an adjustable constant please
        else:
            for potion in potions:
                catalog.append(
                    {
                        "sku": potion["sku"],
                        "name": potion["name"],
                        "quantity": potion["quantity"],
                        "price": int((1 + potion["weight"]) * 35),
                        "potion_type": potion["potion_type"]
                    }
                )
        
    except Exception:
        print("Error occured while fetching data.")
    
    print(catalog)
    return catalog
