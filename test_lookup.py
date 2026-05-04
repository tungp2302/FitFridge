#!/usr/bin/env python3
from pathlib import Path
import sys

# ensure repo root is on sys.path so `flaskr` package imports work when run from project root
sys.path.insert(0, str(Path(__file__).resolve().parent))

from flaskr.api_db.external import openfoodfacts_client as ofc


def print_result(r):
    if not r:
        print('No product found')
        return
    keys = [
        'name', 'brand', 'barcode', 'total_amount', 'unit', 'kcal_per_100g',
        'protein_per_100g', 'fat_per_100g', 'carbs_per_100g', 'sugar_per_100g'
    ]
    for k in keys:
        print(f"{k}: {r.get(k)}")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Lookup product by barcode or name using OpenFoodFacts client')
    parser.add_argument('query', nargs='?', help='Barcode or product name (if omitted, prompts)')
    args = parser.parse_args()

    if args.query:
        q = args.query
    else:
        q = input('Enter barcode or product name: ').strip()

    try:
        res = ofc.lookup_product(q, user_agent='FitFridge/1.0 (test script)')
    except Exception as e:
        print('Lookup error:', e)
        res = None
    print_result(res)
