class FridgeItem:
    """Ein Produkt aus dem Kühlschrank"""

    def __init__(self, product, current_amount, unit):
        self.product = product
        self.current_amount = current_amount
        self.unit = unit

    def consume(self, amount):
        """Gibt den Restwert des Produktes an, nachdem Etwas davon rausgenommen wurde, amount ist die rausgenommene Menge"""
        if amount > self.current_amount:
            print("Fehler: Du willst", amount, self.unit, "verbrauchen, aber es sind nur", self.current_amount, self.unit, "da.")
            return
        self.current_amount = self.current_amount - amount
        print(amount, self.unit, self.product.name, "verbraucht. Rest:", self.current_amount, self.unit)

    def refill(self, amount):
        """Ein Produkt wird aufgefüllt. amount ist wie viel aufgefüllt wird. Gibt danach den neuen Bestand an"""
        self.current_amount = self.current_amount + amount
        print(amount, self.unit, self.product.name, "aufgefüllt. Neuer Stand:", self.current_amount, self.unit)

    def show(self):
        """Sagt wie viel Bestand im Kühlschrank ist"""
        print(self.product.name + " (" + self.product.brand + "): " + str(self.current_amount) + self.unit)