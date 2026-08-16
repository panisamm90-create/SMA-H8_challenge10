import json 
import pandas as pd
import csv
input = 'dataset/vehicles/vehicles.csv'
output = 'dataset/vehicles/vehicles.json'
with open(input, 'r', encoding='utf-8-sig', newline='') as file:
    reader = csv.DictReader(file)
    data = list(reader)
with open(output, 'w', encoding='utf-8') as json_file:
    json.dump(data,json_file)
