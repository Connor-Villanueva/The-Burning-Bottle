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
                connection.execute(sqlalchemy.text("INSERT INTO customer_carts (cart_id) VALUES (:customer_id)"), 
                                   {
                                       "customer_id": customer_id
                                   })

    return "OK"
                

@router.post("/")
def create_cart(new_cart: Customer):
    """ """
    #Since each customer has a cart, find the cart, reset all values, return cart_id
    with db.engine.begin() as connection:
        user_id = connection.execute(sqlalchemy.text("SELECT customer_id FROM customers WHERE name = :name and class = :class and level = :level"), 
                                     {
                                         "name": new_cart.customer_name,
                                         "class": new_cart.character_class,
                                         "level": new_cart.level
                                     }).fetchone()[0]
        
        connection.execute(sqlalchemy.text("UPDATE customer_carts SET item_sku = DEFAULT WHERE cart_id = :user_id"),
                           {
                               "cart_id": user_id
                           })
    
    return {"cart_id": user_id}

class CartItem(BaseModel):
    quantity: int


@router.post("/{cart_id}/items/{item_sku}")
def set_item_quantity(cart_id: int, item_sku: str, cart_item: CartItem):
    """ """

    with db.engine.begin() as connection:
        connection.execute(sqlalchemy.text("UPDATE customer_carts SET item_sku = CONCAT(item_sku, :item_sku)"), 
        {
            "item_sku" : f"{item_sku}:{cart_item.quantity},"
        })
    return "OK"


class CartCheckout(BaseModel):
    payment: str

@router.post("/{cart_id}/checkout")
def checkout(cart_id: int, cart_checkout: CartCheckout):
    """ """
    print(cart_checkout.payment)

    profit = 0
    potions_sold = 0

    with db.engine.begin() as connection:
        item_skus : str = connection.execute(sqlalchemy.text("SELECT item_sku FROM customer_carts WHERE cart_id = :cart_id"), 
        {
            "cart_id" : cart_id
        }).fetchone()[0]
        
        items_purchased = [x.split(":") for x in item_skus.split(',')]
        print(items_purchased[:-1])

        for item in items_purchased[:-1]:
            price = connection.execute(sqlalchemy.text("UPDATE potion_inventory SET potion_quantity = potion_quantity - :quantity WHERE potion_sku = :potion_sku RETURNING potion_price"), 
            {
                "potion_sku": item[0],
                "quantity": int(item[1])
            }).fetchone()[0]
            profit += int(item[1]) * price
            potions_sold += int(item[1])
        
        connection.execute(sqlalchemy.text("UPDATE global_inventory SET gold = gold + :profit"), 
        {
            "profit": profit
        })

    return {"total_potions_bought": potions_sold, "total_gold_paid": profit}
