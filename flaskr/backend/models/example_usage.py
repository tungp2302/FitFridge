"""
Beispiele zur Benutzung der Backend-Klassen Product und FridgeItem.

Diese Datei dient nur als Anschauung und Dokumentation.
Sie wird NICHT von der App benutzt.

Hinweise für das Team:
- Tung: So kannst du nach API-Calls Product-Objekte erstellen.
- Mika: So sehen die Daten aus, die du im Frontend anzeigen kannst.

Ausführen mit:
    python flaskr/backend/models/example_usage.py
"""

from flaskr.backend.models.product import Product
from flaskr.backend.models.fridge_item import FridgeItem


# ============================================
# BEISPIEL 1: Ein Product erstellen
# ============================================
# Hier kämen die Daten normalerweise von der Open Food Facts API.
# Diese Werte hier sind echte Nutella-Werte zum Testen.

nutella_product = Product(
    name="Nutella",
    brand="Ferrero",
    barcode="3017620422003",
    kcal_per_100g=539,
    protein_per_100g=6.3,
    fat_per_100g=30.9,
    carbs_per_100g=57.5
)

print("=== BEISPIEL 1: Product erstellt ===")
nutella_product.show()
print()


# ============================================
# BEISPIEL 2: Product in den Kühlschrank legen
# ============================================
# Wenn der User ein Produkt zum Kühlschrank hinzufügt,
# wird ein FridgeItem aus dem Product erstellt.

nutella_im_kuehlschrank = FridgeItem(
    product=nutella_product,
    current_amount=500,
    unit="g"
)

print("=== BEISPIEL 2: Im Kühlschrank ===")
nutella_im_kuehlschrank.show()
print()


# ============================================
# BEISPIEL 3: Etwas verbrauchen
# ============================================

print("=== BEISPIEL 3: 30g verbraucht ===")
nutella_im_kuehlschrank.consume(30)
nutella_im_kuehlschrank.show()
print()


# ============================================
# BEISPIEL 4: Auffüllen (z.B. zweite Packung)
# ============================================

print("=== BEISPIEL 4: Neue Packung gekauft ===")
nutella_im_kuehlschrank.refill(500)
nutella_im_kuehlschrank.show()
print()


# ============================================
# BEISPIEL 5: Fehler-Fall
# ============================================
# Was passiert, wenn man zu viel verbrauchen will?

print("=== BEISPIEL 5: Zu viel verbrauchen ===")
nutella_im_kuehlschrank.consume(99999)
nutella_im_kuehlschrank.show()
print()


# ============================================
# BEISPIEL 6: Auf Nährwerte zugreifen
# ============================================
# So kommt man von einem FridgeItem an die Nährwerte des verbundenen Produkts.

print("=== BEISPIEL 6: Zugriff auf Nährwerte ===")
print("Produktname:", nutella_im_kuehlschrank.product.name)
print("Marke:", nutella_im_kuehlschrank.product.brand)
print("Aktuelle Menge:", nutella_im_kuehlschrank.current_amount, nutella_im_kuehlschrank.unit)
print("Kalorien pro 100g:", nutella_im_kuehlschrank.product.kcal_per_100g, "kcal")