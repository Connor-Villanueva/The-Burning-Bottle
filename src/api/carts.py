from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from src.api import auth
from enum import Enum
import sqlalchemy
from src import database as db
from datetime import datetime

router = APIRouter(
    prefix="/carts",
    tags=["cart"],
    dependencies=[Depends(auth.get_api_key)],
)

class search_sort_options(str, Enum):
    customer_name = "customer_name"
    item_sku = "item_sku"
    line_item_total = "line_item_total"
    timestamp = "timestamp"

class search_sort_order(str, Enum):
    asc = "asc"
    desc = "desc"   

@router.get("/search/", tags=["search"])
def search_orders(
    customer_name: str = "",
    potion_sku: str = "",
    search_page: str = "",
    sort_col: search_sort_options = search_sort_options.timestamp,
    sort_order: search_sort_order = search_sort_order.desc,
):
    """
    Search for cart line items by customer name and/or potion sku.

    Customer name and potion sku filter to orders that contain the 
    string (case insensitive). If the filters aren't provided, no
    filtering occurs on the respective search term.

    Search page is a cursor for pagination. The response to this
    search endpoint will return previous or next if there is a
    previous or next page of results available. The token passed
    in that search response can be passed in the next search request
    as search page to get that page of results.

    Sort col is which column to sort by and sort order is the direction
    of the search. They default to searching by timestamp of the order
    in descending order.

    The response itself contains a previous and next page token (if
    such pages exist) and the results as an array of line items. Each
    line item contains the line item id (must be unique), item sku, 
    customer name, line item total (in gold), and timestamp of the order.
    Your results must be paginated, the max results you can return at any
    time is 5 total line items.
    """

    results = []
    search_page = int(search_page) if search_page is not "" else 0
    
    with db.engine.begin() as connection:
        search_result = connection.execute(sqlalchemy.text(
            f"""
            SELECT
                line_item_id, customer_name, quantity, item_sku, line_item_total, timestamp
            FROM
                search_orders
            WHERE
                1=1
                {"and customer_name ilike :customer_name" if customer_name != "" else ""}
                {"and item_sku ilike :potion_sku" if potion_sku != "" else ""}
            ORDER BY
                {sort_col.value} {sort_order.value}
            LIMIT 5 OFFSET :page
             """
        ), {
            "customer_name": "%" + customer_name + "%",
            "potion_sku": "%" + potion_sku + "%",
            "page": search_page
        })
    
    for row in search_result:
        results.append(
            {
                "line_item_id": row.line_item_id,
                "item_sku": f"{row.quantity} {row.item_sku}",
                "customer_name": row.customer_name,
                "line_item_total": row.line_item_total,
                "timestamp": row.timestamp
            }
        )

    return {
        "previous": "" if int(search_page) < 5 else f"{int(search_page)-5}",
        "next": "" if int(search_page) - 5 > 0 else f"{int(search_page) + 5}",
        "results": results,
    }

class Customer(BaseModel):
    customer_name: str
    character_class: str
    level: int

@router.post("/visits/{visit_id}")
def post_visits(visit_id: int, customers: list[Customer]):
    """
    Which customers visited the shop today?
    """
    print(f"Customer visits: {customers}\n")

    class_visits = {
        "Barbarian": 0,
        "Bard": 0,
        "Cleric": 0,
        "Druid": 0,
        "Fighter": 0,
        "Monk": 0,
        "Paladin": 0,
        "Ranger": 0,
        "Rogue": 0,
        "Warlock": 0,
        "Wizard": 0
    }

    for customer in customers:
        class_visits[customer.character_class] += 1
    
    # Keep track of the number of visitors per tick
    with db.engine.begin() as connection:
        connection.execute(sqlalchemy.text(
            """
            UPDATE
                ticks
            SET 
                visits = :visits
            WHERE
                id = (SELECT id FROM current_tick)
            """
        ), {"visits": [int(i) for i in class_visits.values()]})
    print(class_visits)
    return "OK"
                

@router.post("/")
def create_cart(new_cart: Customer):
    """ """
    # 1. Add customer to customers table if not already
    # 2. Assign customer a cart
    with db.engine.begin() as connection:
        customer = connection.execute(sqlalchemy.text(
            """
            SELECT check_customer_exists(:name, :class, :level) as verified
            """
        ), {
            "name": new_cart.customer_name,
            "class": new_cart.character_class,
            "level": new_cart.level
        }).one()

        if (not customer.verified):
            connection.execute(sqlalchemy.text(
                """
                INSERT INTO
                    customers (name, class, level)
                VALUES
                    (:name, :class, :level)
                """
            ), {
                "name": new_cart.customer_name,
                "class": new_cart.character_class,
                "level": new_cart.level
            })
        
        cart_id = connection.execute(sqlalchemy.text(
            """
            INSERT INTO
                customer_to_carts (customer_id)
                (
                    SELECT id
                    FROM customers
                    WHERE name = :name and class = :class and level = :level
                )
            RETURNING cart_id
            """
        ),{
            "name": new_cart.customer_name,
            "class": new_cart.character_class,
            "level": new_cart.level
        }).one()
        
    
    return {"cart_id": cart_id.cart_id}

class CartItem(BaseModel):
    quantity: int


@router.post("/{cart_id}/items/{item_sku}")
def set_item_quantity(cart_id: int, item_sku: str, cart_item: CartItem):
    """ """
    with db.engine.begin() as connection:
        connection.execute(sqlalchemy.text(
            """
            INSERT INTO
                cart_items (id, potion_sku, quantity)
            VALUES
                (:cart_id, :item_sku, :quantity)
            """
        ), {
            "cart_id": cart_id,
            "item_sku": item_sku,
            "quantity": cart_item.quantity
        })
        
    return "OK"


class CartCheckout(BaseModel):
    payment: str

@router.post("/{cart_id}/checkout")
def checkout(cart_id: int, cart_checkout: CartCheckout):
    """ """
    with db.engine.begin() as connection:
        items_purchased = connection.execute(sqlalchemy.text(
            """
            SELECT
                potion_sku, quantity, price
            FROM
                cart_items
            JOIN
                potions on potion_sku = potions.sku
            WHERE
                id = :cart_id
            """
        ), {"cart_id": cart_id})

        gold = 0
        potions_sold = 0
        
        # Assuming a single customer can buy multiple potion types, checkout each potion
        # Also add their order to completed orders
        # On average, only executes once per customer
        for item in items_purchased:

            # Checkout cart, return cart_id
            order_id = connection.execute(sqlalchemy.text(
                """
                INSERT INTO
                    completed_orders (customer_id, potion_sku, quantity, tick, cost)
                    (
                        SELECT customer_id, :potion_sku, :quantity, current_tick.id, :cost
                        FROM customer_to_carts
                        JOIN current_tick ON 1=1
                        WHERE cart_id = :cart_id
                    )
                RETURNING id
                """
            ), {"potion_sku": item.potion_sku, "quantity": item.quantity, "cart_id": cart_id, "cost": item.price * item.quantity}).one()

            # Add order to completed_orders using the cart_id as order_id
            connection.execute(sqlalchemy.text(
                """
                INSERT INTO
                    potion_ledger (transaction_type, transaction_id, potion_sku, quantity)
                VALUES
                    ('sold', :order_id, :potion_sku, -:quantity)
                """
            ), {"order_id": order_id.id, "potion_sku": item.potion_sku, "quantity": item.quantity})

            gold += item.price * item.quantity
            potions_sold += item.quantity

        connection.execute(sqlalchemy.text(
            """
            INSERT INTO
                gold_ledger (transaction_type, transaction_id, gold)
            VALUES
                ('potion', :order_id, :gold)
            """
        ), {"order_id": order_id.id, "gold": gold})

    return {"total_potions_bought": potions_sold, "total_gold_paid": gold}
