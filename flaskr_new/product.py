"""
Datenmodell für ein Produkt aus der Open Food Facts Datenbank.

Diese Datei definiert die Klasse `Product`, die einen Lebensmittel-Typ
repräsentiert (z.B. "Nutella von Ferrero"). Konkrete Packungen mit
Restmenge im Kühlschrank werden in fridge_item.py modelliert.
"""

class Product:
    """
    Bauplan für ein Produkt aus der Open Food Facts Datenbank.

    Enthält die festen Eigenschaften eines Lebensmittels: Name, Marke,
    Barcode und Nährwerte pro 100g. Diese Daten ändern sich nicht.

    Eine konkrete Packung mit veränderlicher Restmenge im Kühlschrank
    wird durch die Klasse FridgeItem modelliert.

    Beispiel (Daten ohne API):
        nutella = Product(
            name="Nutella",
            brand="Ferrero",
            barcode="3017620422003",
            kcal_per_100g=539,
            protein_per_100g=6.3,
            fat_per_100g=30.9,
            carbs_per_100g=57.5
        )
    """

    
    def __init__(self, name, brand, barcode,
                kcal_per_100g, protein_per_100g,
                fat_per_100g, carbs_per_100g):
        """
        Erstellt ein neues Product.

        Parameter:
            name (str): Produktname, z.B. "Nutella"
            brand (str): Marke, z.B. "Ferrero"
            barcode (str): Barcode als String (auch wenn nur Zahlen drin sind)
            kcal_per_100g (float): Kalorien pro 100g des Produkts
            protein_per_100g (float): Eiweiß in Gramm pro 100g
            fat_per_100g (float): Fett in Gramm pro 100g
            carbs_per_100g (float): Kohlenhydrate in Gramm pro 100g
        """
        self.name = name
        self.brand = brand
        self.barcode = barcode
        self.kcal_per_100g = kcal_per_100g
        self.protein_per_100g = protein_per_100g
        self.fat_per_100g = fat_per_100g
        self.carbs_per_100g = carbs_per_100g


    def show(self):
        """
        Gibt die Produktinformationen formatiert auf der Konsole aus.
        Wird hauptsächlich für Tests und Debugging benutzt.
        """    
        print(self.name + " (" + self.brand + ")")
        print(" Kalorien: " + str(self.kcal_per_100g) + " kcal/100g")
        print(" Protein:  " + str(self.protein_per_100g) + " g/100g")
        print(" Fett:     " + str(self.fat_per_100g) + " g/100g")
        print(" Kohlenh.: " + str(self.carbs_per_100g) + " g/100g")
