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
                WITH
                current_day AS (
                    SELECT latest_day as day
                    FROM time_info
                ),
                daily_total AS (
                    SELECT day, sum(quantity) as daily_total
                    FROM completed_orders co
                    GROUP BY co.day
                ),
                top_relative_proportions AS (
                    SELECT co.potion_sku, ROUND(SUM(co.quantity)::decimal / dt.daily_total, 2) AS relative_potion_probability
                    FROM completed_orders co
                    JOIN daily_total dt ON co.day = dt.day
                    JOIN current_day cd ON co.day = cd.day
                    GROUP BY co.potion_sku, co.day, dt.daily_total
                    HAVING ROUND(SUM(co.quantity)::decimal / dt.daily_total, 2) > 0.25
                    ORDER BY relative_potion_probability DESC
                    LIMIT 6
                ),
                top_quantities AS (
                    SELECT potion_sku, potion_quantity
                    FROM potion_inventory
                    GROUP BY potion_sku
                    ORDER BY potion_quantity DESC
                    LIMIT 6
                )

            SELECT DISTINCT p.potion_sku, p.potion_name, p.potion_quantity, p.potion_price, p.potion_type, priority
            FROM (
                SELECT potion_sku, 1 AS priority FROM top_relative_proportions
                UNION
                SELECT potion_sku, 2 AS priority FROM top_quantities
            ) AS combined_results
            JOIN potion_inventory p ON combined_results.potion_sku = p.potion_sku
            WHERE p.potion_quantity > 0
            ORDER BY priority, potion_sku
            LIMIT 6
        '''
        )).fetchall()


        for potion in potions:                
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
