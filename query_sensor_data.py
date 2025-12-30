#!/usr/bin/env python3
"""
Simple command-line tool to query sensor data
Makes it easy to filter and export data without needing URLs
"""

import sqlite3
import csv
import sys
import os
from datetime import datetime, timedelta

# Use absolute path so script can run from any directory
DB_FILE = os.path.expanduser("/home/terry/env_home/sensor_data.db")


def show_stats():
    """Show basic statistics about the data"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Total records
    cursor.execute("SELECT COUNT(*) FROM sensor_readings")
    total = cursor.fetchone()[0]
    
    # Date range
    cursor.execute("SELECT MIN(time), MAX(time) FROM sensor_readings")
    min_date, max_date = cursor.fetchone()
    
    # Temperature stats
    cursor.execute("SELECT MIN(temperature), MAX(temperature), AVG(temperature) FROM sensor_readings")
    temp_stats = cursor.fetchone()
    
    # Humidity stats
    cursor.execute("SELECT MIN(humidity), MAX(humidity), AVG(humidity) FROM sensor_readings")
    humidity_stats = cursor.fetchone()
    
    conn.close()
    
    print("\n" + "=" * 60)
    print("DATABASE STATISTICS")
    print("=" * 60)
    print(f"Total Records: {total}")
    if total > 0:
        print(f"Date Range: {min_date} to {max_date}")
        print(f"\nTemperature: {temp_stats[0]:.1f}°C to {temp_stats[1]:.1f}°C (avg: {temp_stats[2]:.1f}°C)")
        print(f"Humidity: {humidity_stats[0]:.1f}% to {humidity_stats[1]:.1f}% (avg: {humidity_stats[2]:.1f}%)")
    print("=" * 60 + "\n")


def latest_reading():
    """Show the latest reading"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM sensor_readings ORDER BY time DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    
    if row:
        print("\n" + "=" * 60)
        print("LATEST READING")
        print("=" * 60)
        print(f"Time: {row['time']}")
        print(f"Temperature: {row['temperature']:.1f}°C")
        print(f"Humidity: {row['humidity']:.1f}%")
        print(f"Pressure: {row['pressure']:.1f} hPa")
        print(f"Gas: {row['gas']:.1f} KOhm")
        print(f"Air Quality: {row['aqi']:.1f}")
        print(f"Est. CO2: {row['co2']:.1f} ppm")
        print(f"Calibrated: {row['calibrated']}")
        print("=" * 60 + "\n")
    else:
        print("No data available\n")


def query_data(temp_min=None, temp_max=None, humidity_min=None, humidity_max=None,
               aqi_min=None, aqi_max=None, co2_min=None, co2_max=None,
               start_date=None, end_date=None, limit=1440):
    """
    Query the database with filters
    Returns matching records
    """
    query_sql = "SELECT * FROM sensor_readings WHERE 1=1"
    params = []
    
    if temp_min is not None:
        query_sql += " AND temperature >= ?"
        params.append(temp_min)
    if temp_max is not None:
        query_sql += " AND temperature <= ?"
        params.append(temp_max)
    if humidity_min is not None:
        query_sql += " AND humidity >= ?"
        params.append(humidity_min)
    if humidity_max is not None:
        query_sql += " AND humidity <= ?"
        params.append(humidity_max)
    if aqi_min is not None:
        query_sql += " AND aqi >= ?"
        params.append(aqi_min)
    if aqi_max is not None:
        query_sql += " AND aqi <= ?"
        params.append(aqi_max)
    if co2_min is not None:
        query_sql += " AND co2 >= ?"
        params.append(co2_min)
    if co2_max is not None:
        query_sql += " AND co2 <= ?"
        params.append(co2_max)
    if start_date:
        query_sql += " AND time >= ?"
        params.append(f"{start_date} 00:00")
    if end_date:
        query_sql += " AND time <= ?"
        params.append(f"{end_date} 23:59")
    
    query_sql += " ORDER BY time ASC LIMIT ?"
    params.append(limit)
    
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query_sql, params)
    rows = cursor.fetchall()
    conn.close()
    
    return rows


def get_recent_readings(limit=60):
    """
    Get the most recent readings (newest first for display)
    """
    query_sql = "SELECT * FROM sensor_readings ORDER BY time DESC LIMIT ?"
    
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query_sql, (limit,))
    rows = cursor.fetchall()
    conn.close()
    
    return rows


def get_last_24_hours():
    """
    Get all readings from the last 24 hours
    """
    # Calculate time 24 hours ago from now
    now = datetime.now()
    twenty_four_hours_ago = now - timedelta(hours=24)
    
    # Format for SQL query
    cutoff_time = twenty_four_hours_ago.strftime('%Y-%m-%d %H:%M')
    
    query_sql = "SELECT * FROM sensor_readings WHERE time >= ? ORDER BY time ASC"
    
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query_sql, (cutoff_time,))
    rows = cursor.fetchall()
    conn.close()
    
    return rows, cutoff_time


def export_to_csv(rows, filename=None):
    """Export query results to CSV"""
    # Create queries directory if it doesn't exist
    queries_dir = os.path.expanduser("/home/terry/env_home/queries")
    os.makedirs(queries_dir, exist_ok=True)
    
    if not filename:
        filename = f"sensor_export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    
    # Full path to save in queries folder
    filepath = os.path.join(queries_dir, filename)
    
    with open(filepath, 'w', newline='') as f:
        if rows:
            writer = csv.writer(f)
            # Write header
            writer.writerow(rows[0].keys())
            
            # Write data with formatted numbers
            for row in rows:
                formatted_row = []
                for key in row.keys():
                    value = row[key]
                    # Format numeric columns with 1 decimal place
                    if key in ['temperature', 'humidity', 'pressure', 'gas', 'aqi', 'co2']:
                        formatted_row.append(f"{float(value):.1f}")
                    else:
                        formatted_row.append(value)
                writer.writerow(formatted_row)
    
    return filepath


def print_menu():
    """Print the interactive menu"""
    print("\n" + "=" * 60)
    print("SENSOR DATA QUERY TOOL")
    print("=" * 60)
    print("1. Show statistics")
    print("2. Show latest reading")
    print("3. Query and export data")
    print("4. Show last 60 readings")
    print("5. Show last 24 hours")
    print("6. Exit")
    print("=" * 60)


def main():
    """Main interactive menu"""
    while True:
        print_menu()
        choice = input("\nSelect option (1-6): ").strip()
        
        if choice == "1":
            show_stats()
            
        elif choice == "2":
            latest_reading()
            
        elif choice == "3":
            print("\nEnter query parameters (press Enter to skip any):")
            
            temp_min = input("  Temperature min (°C): ").strip()
            temp_min = float(temp_min) if temp_min else None
            
            temp_max = input("  Temperature max (°C): ").strip()
            temp_max = float(temp_max) if temp_max else None
            
            humidity_min = input("  Humidity min (%): ").strip()
            humidity_min = float(humidity_min) if humidity_min else None
            
            humidity_max = input("  Humidity max (%): ").strip()
            humidity_max = float(humidity_max) if humidity_max else None
            
            aqi_min = input("  AQI min: ").strip()
            aqi_min = float(aqi_min) if aqi_min else None
            
            aqi_max = input("  AQI max: ").strip()
            aqi_max = float(aqi_max) if aqi_max else None
            
            co2_min = input("  CO2 min (ppm): ").strip()
            co2_min = float(co2_min) if co2_min else None
            
            co2_max = input("  CO2 max (ppm): ").strip()
            co2_max = float(co2_max) if co2_max else None
            
            start_date = input("  Start date (YYYY-MM-DD): ").strip()
            start_date = start_date if start_date else None
            
            end_date = input("  End date (YYYY-MM-DD): ").strip()
            end_date = end_date if end_date else None
            
            limit = input("  Max results (default 1440): ").strip()
            limit = int(limit) if limit else 1440
            
            print("\nQuerying database...")
            rows = query_data(temp_min, temp_max, humidity_min, humidity_max,
                            aqi_min, aqi_max, co2_min, co2_max,
                            start_date, end_date, limit)
            
            print(f"\nFound {len(rows)} matching records")
            
            if rows:
                export = input("Export to CSV? (y/n): ").strip().lower()
                if export == 'y':
                    filename = export_to_csv(rows)
                    print(f"\nExported to: {filename}")
                else:
                    # Show first 5 records
                    print("\nFirst 5 records:")
                    for i, row in enumerate(rows[:5]):
                        print(f"\n  Record {i+1}:")
                        print(f"    Time: {row['time']}")
                        print(f"    Temp: {row['temperature']:.1f}°C, Humidity: {row['humidity']:.1f}%")
                        print(f"    AQI: {row['aqi']:.1f}, CO2: {row['co2']:.1f} ppm")
        
        elif choice == "4":
            print("\nLast 60 readings (oldest to newest):")
            rows = get_recent_readings(limit=60)
            # Reverse the list so oldest shows first
            rows = list(reversed(rows))
            for i, row in enumerate(rows, start=1):
                print(f"\n  {i}. {row['time']}")
                print(f"     Temp: {row['temperature']:.1f}°C, Humidity: {row['humidity']:.1f}%")
                print(f"     AQI: {row['aqi']:.1f}, CO2: {row['co2']:.1f} ppm")
        
        elif choice == "5":
            print("\nFetching last 24 hours of data...")
            rows, cutoff_time = get_last_24_hours()
            
            if rows:
                print(f"\nFound {len(rows)} records from the last 24 hours")
                print(f"Period: {cutoff_time} to {datetime.now().strftime('%Y-%m-%d %H:%M')}")
                
                # Calculate some quick stats
                temps = [row['temperature'] for row in rows]
                humidities = [row['humidity'] for row in rows]
                aqis = [row['aqi'] for row in rows]
                co2s = [row['co2'] for row in rows]
                
                print("\n" + "=" * 60)
                print("24-HOUR SUMMARY")
                print("=" * 60)
                print(f"Temperature: {min(temps):.1f}°C to {max(temps):.1f}°C (avg: {sum(temps)/len(temps):.1f}°C)")
                print(f"Humidity: {min(humidities):.1f}% to {max(humidities):.1f}% (avg: {sum(humidities)/len(humidities):.1f}%)")
                print(f"AQI: {min(aqis):.1f} to {max(aqis):.1f} (avg: {sum(aqis)/len(aqis):.1f})")
                print(f"CO2: {min(co2s):.1f} to {max(co2s):.1f} ppm (avg: {sum(co2s)/len(co2s):.1f} ppm)")
                print("=" * 60)
                
                export = input("\nExport to CSV? (y/n): ").strip().lower()
                if export == 'y':
                    filename = export_to_csv(rows, f"last_24h_{datetime.now().strftime('%Y%m%d_%H%M')}.csv")
                    print(f"\nExported to: {filename}")
            else:
                print("\nNo data found for the last 24 hours")
        
        elif choice == "6":
            print("\nGoodbye!\n")
            break
        
        else:
            print("\nInvalid choice. Please select 1-6.")


if __name__ == "__main__":
    # Check if database exists
    import os
    if not os.path.exists(DB_FILE):
        print(f"\nError: Database file '{DB_FILE}' not found!")
        print("Make sure the server has run at least once to create the database.\n")
        sys.exit(1)
    
    main()
