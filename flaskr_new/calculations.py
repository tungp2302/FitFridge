"""Hilfsfunktionen für Nährwert- und Mengenberechnungen.

Dieses Modul stellt allgemeine Berechnungshilfen bereit, die in
verschiedenen Teilen der App benötigt werden:
- Prozentuale Anteile (z.B. Anteil an Tageskalorien)
- Einheiten-Konvertierung (z.B. kg zu g, l zu ml)
"""

def to_percentage(part, total):
    """
    Berechnet den prozentualen Anteil von `part` an `total`.

    Beispiel:
        to_percentage(30, 200) → 15.0
        Bedeutet: 30 sind 15% von 200.

    Parameter:
        part (float): Teilmenge
        total (float): Gesamtmenge

    Returns:
        float: Prozentualer Anteil (0 bis 100)

    Hinweise:
        - Wenn total == 0, wird 0.0 zurückgegeben (kein Division-Fehler)
    """
    if total == 0:
        return 0.0
    return (part / total) * 100

def convert_units(amount, from_unit, to_unit):
    """
    Konvertiert eine Menge zwischen kompatiblen Einheiten.

    Unterstützte Einheiten:
        Gewicht:  mg, g, kg
        Volumen:  ml, cl, l

    Beispiele:
        convert_units(1.5, "kg", "g")  → 1500.0
        convert_units(500, "ml", "l")  → 0.5
        convert_units(100, "g", "g")   → 100.0

    Parameter:
        amount (float): Menge, die konvertiert werden soll
        from_unit (str): Ausgangseinheit
        to_unit (str): Zieleinheit

    Returns:
        float: Konvertierte Menge

    Raises:
        ValueError: Wenn die Einheiten nicht kompatibel sind
                    (z.B. Gewicht zu Volumen geht nicht ohne Dichte)
    """
    # Umrechnungsfaktoren in die Basiseinheit
    # Gewicht: alles zu g
    # Volumen: alles zu ml
    weight_units = {"mg": 0.001, "g": 1.0, "kg": 1000.0}
    volume_units = {"ml": 1.0, "cl" : 10.0, "l": 1000.0}

    # Beide Einheiten müssen aus der gleichen Kategorie sein
    if from_unit in weight_units and to_unit in weight_units:
        amount_in_base = amount * weight_units[from_unit]
        return amount_in_base / weight_units[to_unit]
    
    if from_unit in volume_units and to_unit in volume_units:
        amount_in_base = amount * volume_units[from_unit]
        return amount_in_base / volume_units[to_unit]
    
    raise ValueError(
        f"Cannot convert from '{from_unit}' to '{to_unit}'. "
        f"Weight units: mg, g, kg, Volume units: ml, cl, l."
    )
