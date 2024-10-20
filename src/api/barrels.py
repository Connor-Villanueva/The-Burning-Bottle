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
    

    ml_total = get_total_ml(barrels_delivered)

    with db.engine.begin() as connection:
        connection.execute(sqlalchemy.text(
            "INSERT INTO barrel_ledger (red_ml, green_ml, blue_ml, dark_ml) VALUES (:red, :green, :blue, :dark)"
        ),
        {
            'red': ml_total[0],
            'green': ml_total[1],
            'blue': ml_total[2],
            'dark': ml_total[3]
        })
    
    return "OK"

# Calculates total ml delivers of each color
def get_total_ml(barrels: list[Barrel]):
    total_ml = [0, 0, 0, 0]

    for barrel in barrels:
        potion_type = barrel.potion_type.index(max(barrel.potion_type))
        total_ml[potion_type] = barrel.ml_per_barrel * barrel.quantity

    return total_ml

# Gets called once a day
@router.post("/plan")
def get_wholesale_purchase_plan(wholesale_catalog: list[Barrel]):
    """ """
    #print(wholesale_catalog)

    with db.engine.begin() as connection:
        stats = connection.execute(sqlalchemy.text(
            """
                WITH
                    gold as (
                        SELECT SUM(gold) as gold
                        FROM gold_ledger
                    ),
                    current_liquid as (
                        SELECT SUM(red_ml) as red, SUM(green_ml) as green, SUM(blue_ml) as blue, SUM(dark_ml) as dark
                        FROM barrel_ledger
                    ),
                    max_ml as (
                        SELECT SUM(liquids) as max_ml
                        FROM capacity_ledger
                    ),
                    game_stats as (
                        SELECT game_stage
                        FROM game_info
                    )

                SELECT gold, red, green, blue, dark, max_ml, game_stage
                FROM gold
                LEFT JOIN current_liquid ON 1=1
                LEFT JOIN max_ml ON 1=1
                LEFT JOIN game_stats ON 1=1
            """
        )).fetchone()

        top_daily_potion = connection.execute(sqlalchemy.text(
            """
            WITH
                current_day as (
                    SELECT day
                    FROM game_info
                ),
                daily_total as (
                    SELECT co.day, sum(quantity) as total
                    FROM completed_orders co
                    JOIN current_day cd on co.day = cd.day
                    GROUP BY co.day
                ),
                relative_probability as (
                    SELECT p.red, p.green, p.blue, p.dark, ROUND(sum(co.quantity)::numeric / dt.total, 2) as proportion
                    FROM completed_orders AS co
                    JOIN daily_total dt on co.day = dt.day
                    JOIN potions p on p.id = co.potion_id
                    GROUP BY dt.total, p.red, p.green, p.blue, p.dark
                )
            SELECT *
            FROM relative_probability
            WHERE red = 100 OR green = 100 OR blue = 100 OR dark = 100
            ORDER BY proportion DESC
            LIMIT 1
            """
        )).fetchone()

    current_liquids = [stats[1], stats[2], stats[3], stats[4]]
    top_potion = [top_daily_potion[0], top_daily_potion[1], top_daily_potion[2], top_daily_potion[3]]

    return get_barrel_plan(wholesale_catalog, stats[0], current_liquids, stats[5], stats[6], top_potion)

def get_barrel_plan(catalog: list[Barrel], budget: int, liquids: list[int], max_ml: int, game_state: int, top_potion: list[int]):
    #   Get barrel plan based on this info
    purchase_plan = []
    #   1. Determine catalog with game state
    if (game_state == 1):
        catalog = sorted(filter(lambda b: b.ml_per_barrel > 250 and b.ml_per_barrel < 10_000, catalog), key = lambda b: (b.potion_type, b.ml_per_barrel), reverse=True)
    
    elif (game_state == 2):
        catalog = sorted(filter(lambda b: b.ml_per_barrel > 250, catalog), key = lambda b: (b.potion_type, b.ml_per_barrel), reverse=True)
        budget = 0.85 * budget
    
    elif (game_state == 3):
        catalog = sorted(filter(lambda b: b.ml_per_barrel >= 2500, catalog), key = lambda b: (b.potion_type, b.ml_per_barrel), reverse=True)

    if (budget < 400):
        barrel_type = [x//100 for x in top_potion]
        cheapest_barrel = min(filter(lambda b: b.potion_type == barrel_type, catalog), key = lambda b: b.price)

        if (cheapest_barrel.price <= budget):
            purchase_plan.append(
                {
                    "sku": cheapest_barrel.sku,
                    "quantity": budget // cheapest_barrel.price
                }
            )
    else:
        ml_needed_each = [max_ml//4 - x for x in liquids]
        barrel_types = [[1,0,0,0], [0,1,0,0], [0,0,1,0], [0,0,0,1]]

        for x in zip(barrel_types, ml_needed_each):
            max_budget = budget//4
            ml_needed = x[1]
            for barrel in catalog:
                if barrel.potion_type == x[0] and ml_needed > 0:
                    max_qty = ml_needed//barrel.ml_per_barrel
                    max_qty = min(max_qty, max_budget//barrel.price, barrel.quantity)

                    if (max_budget > 0 and max_qty > 0):
                        purchase_plan.append(
                            {
                                "sku": barrel.sku,
                                "quantity": max_qty
                            }
                        )
                        max_budget -= barrel.price * max_qty
                        ml_needed -= barrel.ml_per_barrel * max_qty
    
    return purchase_plan