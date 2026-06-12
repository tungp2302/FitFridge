DROP TABLE IF EXISTS fridge_item;
DROP TABLE IF EXISTS meal_tracker_entry;
DROP TABLE IF EXISTS meal_tracker_settings;
DROP TABLE IF EXISTS app_settings;
DROP TABLE IF EXISTS consumption_log;
DROP TABLE IF EXISTS product;
DROP TABLE IF EXISTS user;

CREATE TABLE user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL
);

CREATE TABLE meal_tracker_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE NOT NULL,
    daily_kcal REAL NOT NULL DEFAULT 2000,
    protein_pct REAL NOT NULL DEFAULT 30,
    carbs_pct REAL NOT NULL DEFAULT 40,
    fat_pct REAL NOT NULL DEFAULT 30,
    updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user (id)
);

CREATE TABLE app_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE NOT NULL,
    llm_model TEXT NOT NULL DEFAULT 'qwen3.5:latest',
    updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user (id)
);

CREATE TABLE product (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    brand TEXT NOT NULL,
    barcode TEXT UNIQUE NOT NULL,
    kcal_per_100g REAL NOT NULL,
    protein_per_100g REAL NOT NULL,
    fat_per_100g REAL NOT NULL,
    carbs_per_100g REAL NOT NULL,
    expiry_date DATE,
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE fridge_item (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    product_id INTEGER NOT NULL,
    current_amount REAL NOT NULL,
    unit TEXT NOT NULL,
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user (id),
    FOREIGN KEY (product_id) REFERENCES product (id)
);

CREATE TABLE consumption_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    event_type TEXT CHECK(event_type IN ('consume','refill')) NOT NULL,
    amount REAL NOT NULL,
    unit TEXT,
    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    note TEXT,
    FOREIGN KEY (product_id) REFERENCES product (id)
);

CREATE TABLE meal_tracker_entry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    meal_name TEXT NOT NULL,
    product_id INTEGER,
    barcode TEXT,
    amount REAL,
    unit TEXT,
    kcal REAL NOT NULL,
    protein_g REAL NOT NULL DEFAULT 0,
    carbs_g REAL NOT NULL DEFAULT 0,
    fat_g REAL NOT NULL DEFAULT 0,
    note TEXT,
    section TEXT,
    eaten_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user (id)
);
