class Product:
    """
    Bauplan für die Open Food Facts Datenbank die Macros, Marke und so
    Das ist nur für das generelle Produkt. Die kühlschrankprodukte sind im ,,fridge_item.py"

    Beispiel ohne der API:

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

    
    def __init__(self, name, brand, barcode, kcal_per_100g, protein_per_100g, fat_per_100g, carbs_per_100g):
        """Erstellt ein neues Produkt"""
        self.name = name
        self.brand = brand
        self.barcode = barcode
        self.kcal_per_100g = kcal_per_100g
        self.protein_per_100g = protein_per_100g
        self.fat_per_100g = fat_per_100g
        self.carbs_per_100g = carbs_per_100g


    def show(self):
        """Zeigt den Namen des Produktes und die Macros pro 100g an"""    
        print(self.name + " (" + self.brand + ")")
        print(" Kalorien: " + str(self.kcal_per_100g) + " kcal/100g")
        print(" Protein:  " + str(self.protein_per_100g) + " g/100g")
        print(" Fett:     " + str(self.fat_per_100g) + " g/100g")
        print(" Kohlenh.: " + str(self.carbs_per_100g) + " g/100g")
