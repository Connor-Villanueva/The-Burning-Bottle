from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db

router = APIRouter(
    prefix="/info",
    tags=["info"],
    dependencies=[Depends(auth.get_api_key)],
)

class Timestamp(BaseModel):
    day: str
    hour: int

@router.post("/current_time")
def post_time(timestamp: Timestamp):
    """
    Share current time.
    """

    print("Day: " + timestamp.day)
    print("Hour: " + str(timestamp.hour))

    days = ['Hearthday', 'Crownday', 'Blesseday', 'Soulday', 'Edgeday', 'Bloomday', 'Arcanaday']
    

    with db.engine.begin() as connection:

        #If new day, calculate probabilities for day before
        if (timestamp.hour == 0):
            last_day :str = connection.execute(sqlalchemy.text("SELECT latest_day FROM time_info")).scalar()

            #To hopefully prevent SQL injection
            if (last_day in days):
                query = f"""
                WITH daily_totals AS (
                    SELECT day, SUM(quantity) AS day_total
                    FROM completed_orders
                    GROUP BY day
                )
                UPDATE potion_distribution pd
                SET {last_day.lower()} = COALESCE(ROUND(co.relative_probability, 2), 0)
                FROM (
                    SELECT co.potion_sku, ROUND(SUM(co.quantity)::decimal / dt.day_total, 2) as relative_probability
                    FROM completed_orders co
                    JOIN daily_totals dt ON co.day = dt.day
                    WHERE co.day = '{last_day}'
                    GROUP BY co.potion_sku, dt.day_total
                ) AS co
                WHERE pd.potion_sku = co.potion_sku;
                """
                connection.execute(sqlalchemy.text(query))
            

        connection.execute(sqlalchemy.text("UPDATE time_info SET latest_day = :day, latest_hour = :hour"),
                           {
                               "day": timestamp.day,
                               "hour": timestamp.hour
                           })

    return "OK"

