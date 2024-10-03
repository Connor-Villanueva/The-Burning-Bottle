from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from src.api import auth
from enum import Enum
import sqlalchemy
from src import database as db

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
        #Check if customer exists in database
        for c in customers:
            result = connection.execute(sqlalchemy.text("SELECT name FROM customers WHERE name = :customer_name"), 
                                        {
                                            'customer_name': c.customer_name
                                        }).fetchone()
            if (result is not None):
                print(f"customer exists: {c.customer_name}")
            else:
                #If customer is not in database, add to customers and create an empty cart with cart_id = user_id
                #This guaratees each customer has a cart
                connection.execute(sqlalchemy.text(f"INSERT INTO customers (name, class, level) VALUES ('{c.customer_name}', '{c.character_class}', {c.level})"))
                user_id = connection.execute(sqlalchemy.text(f"SELECT user_id FROM customers WHERE name = :customer_name"), {'customer_name': c.customer_name}).fetchone()[0]
                connection.execute(sqlalchemy.text(f"INSERT INTO carts (cart_id) VALUES ({user_id})"))

    return "OK"


@router.post("/")
def create_cart(new_cart: Customer):
    """ """
    #Since each customer has a cart, find the cart, reset all values, return cart_id
    with db.engine.begin() as connection:
        user_id = connection.execute(sqlalchemy.text(f"SELECT user_id FROM customers WHERE name = '{new_cart.customer_name}'")).fetchone()[0]

        connection.execute(sqlalchemy.text(f"UPDATE carts SET item_sku = 'none', quantity = 0 WHERE cart_id = {user_id}"))
    
    #cart_id = user_id
    return user_id

class CartItem(BaseModel):
    quantity: int


@router.post("/{cart_id}/items/{item_sku}")
def set_item_quantity(cart_id: int, item_sku: str, cart_item: CartItem):
    """ """
    with db.engine.begin() as connection:
        result = connection.execute(sqlalchemy.text("SELECT item_sku, quantity FROM carts WHERE cart_id = :cart_id"), 
                                  {
                                      "cart_id": cart_id
                                   }).fetchone()
        cart = [item for item in result]
        print(cart)
        if (cart[0] == 'none'):
            cart[0] = item_sku
            cart[1] = cart_item.quantity
        else:
            cart[0] += f", {item_sku}"
            cart[1] += cart_item.quantity
        
        update_item = f"UPDATE carts SET item_sku = '{cart[0]}' WHERE cart_id = {cart_id}"
        update_quantity = f"UPDATE carts SET quantity = {cart[1]} WHERE cart_id = {cart_id}"
        connection.execute(sqlalchemy.text(update_item))
        connection.execute(sqlalchemy.text(update_quantity))


    return "OK"


class CartCheckout(BaseModel):
    payment: str

@router.post("/{cart_id}/checkout")
def checkout(cart_id: int, cart_checkout: CartCheckout):
    """ """
    with db.engine.begin() as connection:
        cart = connection.execute(sqlalchemy.text(f"SELECT item_sku, quantity FROM carts WHERE cart_id = {cart_id}")).fetchone()
        inventory = connection.execute(sqlalchemy.text("SELECT num_green_potions, gold FROM test_inventory")).fetchone()

        #Update inventory
        connection.execute(sqlalchemy.text(
            f"UPDATE global_inventory SET num_green_potions = {inventory[0] - cart[1]}, gold = {inventory[1] + cart[1]*40}"))
    return {"total_potions_bought": cart[1], "total_gold_paid": cart_checkout.payment}
