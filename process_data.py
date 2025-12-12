
import json
import sqlite3

def process_data():
    with open('F-A0010-001.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()

    for location in data['cwaopendata']['resources']['resource']['data']['agrWeatherForecasts']['weatherForecasts']['location']:
        location_name = location['locationName']
        
        # Taking the first day's data
        min_temp = float(location['weatherElements']['MinT']['daily'][0]['temperature'])
        max_temp = float(location['weatherElements']['MaxT']['daily'][0]['temperature'])
        description = location['weatherElements']['Wx']['daily'][0]['weather']

        if location_name and min_temp is not None and max_temp is not None and description:
            cursor.execute('''
            INSERT INTO weather (location, min_temp, max_temp, description)
            VALUES (?, ?, ?, ?)
            ''', (location_name, min_temp, max_temp, description))

    conn.commit()
    conn.close()

if __name__ == '__main__':
    process_data()
