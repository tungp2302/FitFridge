"""
Datenmodell für ein Produkt-Exemplar im Kühlschrank.

Diese Datei definiert die Klasse `FridgeItem`, die eine konkrete Packung
eines Produkts mit veränderlicher Restmenge repräsentiert.
Der allgemeine Produkt-Typ wird in product.py modelliert.
"""

from flaskr.backend.models.product import Product


class FridgeItem:
    """
    Ein konkretes Produkt-Exemplar im Kühlschrank.

    Ein FridgeItem verbindet ein allgemeines Product (Bauplan) mit einer
    aktuellen Restmenge. Die Restmenge ändert sich, wenn etwas verbraucht
    oder aufgefüllt wird.

    Beispiel:
        nutella_product = Product("Nutella", "Ferrero", ...)
        nutella_packung = FridgeItem(
            product=nutella_product,
            current_amount=500,
            unit="g"
        )
        nutella_packung.consume(20)   # 20g verbraucht
        nutella_packung.refill(100)   # 100g aufgefüllt
    """

    def __init__(self, product, current_amount, unit):
        """
        Erstellt ein neues FridgeItem.

        Parameter:
            product (Product): Das verbundene Product-Objekt
                               (siehe flaskr/backend/models/product.py)
            current_amount (float): Aktuelle Restmenge im Kühlschrank
            unit (str): Einheit der Menge, z.B. "g", "ml", "stk"
        """
        self.product = product
        self.current_amount = current_amount
        self.unit = unit

    def consume(self, amount):
        """
        Reduziert die Restmenge um den verbrauchten Anteil.

        Wenn die angegebene Menge größer ist als der aktuelle Bestand,
        wird nichts geändert und eine Fehlermeldung ausgegeben.

        Parameter:
            amount (float): Menge, die verbraucht wird (in der gleichen
                            Einheit wie self.unit)
        """
        if amount > self.current_amount:
            print("Fehler: Du willst", amount, self.unit,
                  "verbrauchen, aber es sind nur",
                  self.current_amount, self.unit, "da.")
            return
        self.current_amount = self.current_amount - amount
        print(amount, self.unit, self.product.name,
              "verbraucht. Rest:", self.current_amount, self.unit)

    def refill(self, amount):
        """
        Erhöht die Restmenge (z.B. wenn eine neue Packung gekauft wurde).

        Parameter:
            amount (float): Menge, die hinzugefügt wird
        """
        self.current_amount = self.current_amount + amount
        print(amount, self.unit, self.product.name,
              "aufgefüllt. Neuer Stand:", self.current_amount, self.unit)

    def show(self):
        """
        Gibt das FridgeItem mit Name, Marke und Restmenge auf der Konsole aus.
        Wird hauptsächlich für Tests und Debugging benutzt.
        """
        print(self.product.name + " (" + self.product.brand + "): "
              + str(self.current_amount) + " " + self.unit)