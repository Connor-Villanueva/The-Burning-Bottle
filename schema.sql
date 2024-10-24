--Time Information: 
create table
  public.time_info (
    id bigint generated by default as identity not null,
    latest_day text null,
    latest_hour integer null,
    constraint time_info_pkey primary key (id)
  ) tablespace pg_default;

--Auto Populates time_info With a Default Day/Hour
insert into time_info (latest_day, latest_hour) VALUES ('Hearthday', 0);


--Contains Potion Information
create table
  public.potion_inventory (
    potion_name text null,
    potion_type integer[] null,
    potion_sku text not null,
    potion_price integer not null default 40,
    potion_quantity integer not null default 0,
    constraint potion_inventory_pkey primary key (potion_sku)
  ) tablespace pg_default;

--Auto Populates sku, type, and price (Can be done with python script)
--See Below For Python Script For Populating Potion Names
DO $$
BEGIN
  FOR r in 0..101 LOOP
    FOR g in 0..101-r LOOP
      FOR b in 0..101-r-g LOOP
        FOR d in 0..101-r-g LOOP
          IF r%20 = 0 AND g%20 = 0 AND b%20 = 0 AND d%20 = 0 AND (r+g+b+d = 100) THEN
            INSERT INTO test_table (potion_sku, potion_type, price)
             VALUES ('RGBD_'|| r || '_' || g || '_' || b || '_' || d, ARRAY[r, g, b, d], 40);
          END IF;
        END LOOP;
      END LOOP;
    END LOOP;
  END LOOP;
END; $$


--Global Shop Information
create table
  public.global_inventory (
    id bigint generated by default as identity not null,
    gold integer not null default 100,
    max_potions integer not null default 50,
    max_ml integer not null default 10000,
    num_red_ml integer not null default 0,
    num_green_ml integer not null default 0,
    num_blue_ml integer not null default 0,
    num_dark_ml integer not null default 0,
    constraint global_inventory_pkey primary key (id)
  ) tablespace pg_default;

--Populate global_inventory With Default Values
INSERT INTO global_inventory 
(gold, max_potions, max_ml, num_red_ml, num_green_ml, num_blue_ml, num_dark_ml) VALUES 
(DEFAULT, DEFAULT, DEFAULT, DEFAULT, DEFAULT, DEFAULT, DEFAULT);


--All Customers Who Have Visited
create table
  public.customers (
    customer_id bigint generated by default as identity not null,
    name text null,
    class text null,
    level integer null,
    created_at timestamp with time zone not null default now(),
    constraint customers_pkey primary key (customer_id),
    constraint customers_customer_id_key unique (customer_id)
  ) tablespace pg_default;


--Linking Customers/Carts: Each Customer Is Assigned A Cart and Reuses Their Cart
create table
  public.customer_cart (
    customer_id bigint not null,
    cart_id bigint not null,
    constraint customer_cart_pkey primary key (customer_id),
    constraint customer_cart_cart_id_key unique (cart_id),
    constraint customer_cart_customer_id_key unique (customer_id),
    constraint customer_cart_customer_id_fkey foreign key (customer_id) references customers (customer_id) on update cascade on delete cascade
  ) tablespace pg_default;


--Completed Orders With Potions Purchased and Time Information
create table
  public.completed_orders (
    order_id bigint generated by default as identity not null,
    customer_id bigint null,
    potion_sku text null,
    quantity integer null,
    day text null,
    hour integer null,
    constraint completed_orders_pkey primary key (order_id),
    constraint completed_orders_customer_id_fkey foreign key (customer_id) references customers (customer_id) on update cascade on delete cascade,
    constraint completed_orders_potion_sku_fkey foreign key (potion_sku) references potion_inventory (potion_sku) on update cascade on delete cascade
  ) tablespace pg_default;


--Carts With Items
create table
  public.cart_items (
    cart_id bigint not null,
    potion_sku text not null,
    quantity integer null,
    constraint cart_items_pkey primary key (cart_id, potion_sku),
    constraint cart_items_cart_id_fkey foreign key (cart_id) references customer_cart (cart_id) on update cascade on delete cascade,
    constraint cart_items_potion_sku_fkey foreign key (potion_sku) references potion_inventory (potion_sku) on update cascade on delete cascade
  ) tablespace pg_default;


--Python Script To Populate Potions Table Taken From Online

-- adjectives = [
--     "Mighty", "Glowing", "Enchanted", "Mystic", "Ancient", "Cursed", 
--     "Divine", "Ethereal", "Flaming", "Frozen", "Shimmering", "Shadowy"
--     ]

--     magic_words = [
--         "Elixir", "Brew", "Potion", "Draught", "Tonic", "Vial", "Concoction", 
--         "Mixture", "Serum", "Essence", "Philter", "Dew"
--     ]

--     # Map the color indices to color names
--     color_map = {
--         0: "Crimson",  # red
--         1: "Emerald",  # green
--         2: "Sapphire", # blue
--         3: "Violet"    # dark
--     }

--     # Function to generate potion names based on the color ratios
--     def generate_potion_name_from_colors(color_ratios):
--         adjective = random.choice(adjectives)
        
--         # Find the dominant color based on the highest value in the list
--         dominant_color_index = color_ratios.index(max(color_ratios))
--         dominant_color = color_map[dominant_color_index]
        
--         # Find the second dominant color (if applicable)
--         sorted_ratios = sorted(color_ratios, reverse=True)
--         second_color = None
--         if sorted_ratios[1] >= 20:  # If the second color is at least 20% of the total
--             second_color_index = color_ratios.index(sorted_ratios[1])
--             second_color = color_map[second_color_index]
        
--         # Create the potion name
--         if second_color:
--             potion_name = f"{adjective} {dominant_color}-{second_color} {random.choice(magic_words)}"
--         else:
--             potion_name = f"{adjective} {dominant_color} {random.choice(magic_words)}"
        
--         return potion_name


--     potion_combinations = []
--     for r in range(0,101,20):
--         for g in range(0,101-r,20):
--             for b in range(0,101-r-g,20):
--                 for d in range(0,101-r-g-b,20):
--                     if (r+g+b+d == 100):
--                         potion_combinations.append([r,g,b,d])

--      with db.engine.begin() as connection
--          for p in potion_combinations:
--              sku = f"RGBD_{p[0]}_{p[1]}_{p[2]}_{p[3]}"
--              name = generate_potion_name_from_colors(p)
--              connection.execute(sqlalchemy.text(
--                  f"UPDATE potions SET (potion_name) = '{name}' WHERE potion_sku = '{sku}'")
--              )
