from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from src.api import auth
from enum import Enum
import sqlalchemy
from src import database as db
import json

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

    return {
        "previous": "",
        "next": "",
        "results": [
            {
                "line_item_id": 1,
                "item_sku": "1 oblivion potion",
                "customer_name": "Scaramouche",
                "line_item_total": 50,
                "timestamp": "2021-01-01T00:00:00Z",
            }
        ],
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
    print(customers)

    with db.engine.begin() as connection:
        for customer in customers:
            customer_exist = connection.execute(sqlalchemy.text(f"SELECT customer_id FROM customers WHERE name = '{customer.customer_name}' AND class = '{customer.character_class}' AND level = {customer.level}")).fetchone()
            
            if (customer_exist is None):
                customer_id = connection.execute(sqlalchemy.text("INSERT INTO customers (name, class, level) VALUES (:name, :class, :level) RETURNING customer_id"), 
                                   {
                                       "name": customer.customer_name,
                                       "class": customer.character_class,
                                       "level": customer.level
                                   }).fetchone()[0]
                connection.execute(sqlalchemy.text("INSERT INTO customer_cart (customer_id, cart_id) VALUES (:customer_id, :cart_id)"), 
                                   {
                                       "customer_id":customer_id,
                                       "cart_id" : customer_id
                                   })

    return "OK"
                

@router.post("/")
def create_cart(new_cart: Customer):
    """ """
    #Since each customer has a cart_id, delete all pre-existing carts from cart_items
    with db.engine.begin() as connection:
        user_id = connection.execute(sqlalchemy.text("SELECT customer_id FROM customers WHERE name = :name and class = :class and level = :level"), 
                                     {
                                         "name": new_cart.customer_name,
                                         "class": new_cart.character_class,
                                         "level": new_cart.level
                                     }).fetchone()[0]
        
        connection.execute(sqlalchemy.text("DELETE FROM cart_items WHERE cart_id = :cart_id"), 
                           {
                               "cart_id": user_id
                           })
    
    return {"cart_id": user_id}

class CartItem(BaseModel):
    quantity: int


@router.post("/{cart_id}/items/{item_sku}")
def set_item_quantity(cart_id: int, item_sku: str, cart_item: CartItem):
    """ """

    #Insert rows into cart_items with sku and quantity
    with db.engine.begin() as connection:
        connection.execute(sqlalchemy.text("INSERT INTO cart_items (cart_id, potion_sku, quantity) VALUES (:cart_id, :potion_sku, :quantity)"),
                           {
                               "cart_id": cart_id,
                               "potion_sku": item_sku,
                               "quantity": cart_item.quantity
                           })
        
    return "OK"


class CartCheckout(BaseModel):
    payment: str

@router.post("/{cart_id}/checkout")
def checkout(cart_id: int, cart_checkout: CartCheckout):
    """ """
    #print(cart_checkout.payment)

    profit = 0
    potions_sold = 0

    with db.engine.begin() as connection:
        items_purchased = connection.execute(sqlalchemy.text("SELECT potion_sku, quantity FROM cart_items WHERE cart_id = :cart_id"),
        {
            "cart_id": cart_id
        }).fetchall()
        
        profit = 0
        potions_sold = sum(p[1] for p in items_purchased)

        for item in items_purchased:
            price = connection.execute(sqlalchemy.text("SELECT potion_price FROM potion_inventory WHERE potion_sku = :potion_sku"),
            {
                "potion_sku": item[0]
            }).fetchone()[0]

            #profit += price * quantity
            profit += price * item[1]

            connection.execute(sqlalchemy.text("UPDATE potion_inventory SET potion_quantity = potion_quantity - :potion_qty WHERE potion_sku = :potion_sku"),
            {
                "potion_qty": item[1],
                "potion_sku": item[0]
            })
        connection.execute(sqlalchemy.text("UPDATE global_inventory SET gold = gold + :profit"),
        {
            "profit":profit
        })


    return {"total_potions_bought": potions_sold, "total_gold_paid": profit}
