#!/usr/bin/env python3
"""
Flask server to receive air quality sensor data from M5Stack
Stores data in SQLite database instead of CSV
"""

import sqlite3
from datetime import datetime

from flask import Flask, jsonify, request

app = Flask(__name__)

# Database file
DB_FILE = "/home/terry/env_home/sensor_data.db"


def init_database():
    """Create the database table if it doesn't exist"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sensor_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time TEXT NOT NULL,
            temperature REAL,
            humidity REAL,
            pressure REAL,
            gas REAL,
            aqi REAL,
            co2 REAL,
            calibrated TEXT
        )
    """)
    
    # Create indexes for faster queries on commonly filtered columns
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_time 
        ON sensor_readings(time)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_temperature 
        ON sensor_readings(temperature)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_humidity 
        ON sensor_readings(humidity)
    """)
    
    conn.commit()
    conn.close()
    print(f"Database initialized: {DB_FILE}")


@app.route("/sensor_data", methods=["POST"])
def receive_data():
    try:
        # Get JSON data from request
        data = request.get_json()

        # Extract and round values to 1 decimal place
        temperature = round(data.get("temperature", 0), 1)
        humidity = round(data.get("humidity", 0), 1)
        pressure = round(data.get("pressure", 0), 1)
        gas = round(data.get("gas_resistance", 0), 1)
        aqi = round(data.get("air_quality_score", 0), 1)
        co2 = round(data.get("estimated_co2", 0), 1)
        calibrated = "true" if data.get("calibrated", False) else "false"

        # Timestamp without seconds (matching CSV format)
        time = datetime.now().strftime("%Y-%m-%d %H:%M")

        # Insert into database
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO sensor_readings 
            (time, temperature, humidity, pressure, gas, aqi, co2, calibrated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (time, temperature, humidity, pressure, gas, aqi, co2, calibrated))
        
        conn.commit()
        conn.close()

        print(f"Data saved: Temp={temperature:.1f}°C, Humidity={humidity:.1f}%, "
              f"Pressure={pressure:.1f}hPa, Gas={gas:.1f}KOhm, "
              f"AQI={aqi:.1f}, CO2={co2:.1f}ppm (cal:{calibrated})")

        return jsonify({"status": "success", "message": "Data saved to database"}), 200

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 400


@app.route("/status", methods=["GET"])
def status():
    """Status check endpoint with record count"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sensor_readings")
        count = cursor.fetchone()[0]
        conn.close()
        
        return jsonify({
            "status": "running",
            "message": "Air Quality Server (SQLite) is active",
            "records": count
        }), 200
    except Exception as e:
        return jsonify({
            "status": "running",
            "message": "Air Quality Server (SQLite) is active",
            "error": str(e)
        }), 200


@app.route("/latest", methods=["GET"])
def latest():
    """Get the most recent reading"""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM sensor_readings 
            ORDER BY time DESC 
            LIMIT 1
        """)
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return jsonify(dict(row)), 200
        else:
            return jsonify({"message": "No data available"}), 404
            
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/query", methods=["GET"])
def query():
    """
    Query database with optional filters and export to CSV
    
    Query parameters:
    - temp_min, temp_max: temperature range
    - humidity_min, humidity_max: humidity range
    - pressure_min, pressure_max: pressure range
    - aqi_min, aqi_max: air quality index range
    - co2_min, co2_max: CO2 range (ppm)
    - start_date, end_date: date range (YYYY-MM-DD format)
    - limit: max number of records (default: 1000)
    - export_csv: if 'true', returns CSV format
    """
    try:
        # Get query parameters
        temp_min = request.args.get("temp_min", type=float)
        temp_max = request.args.get("temp_max", type=float)
        humidity_min = request.args.get("humidity_min", type=float)
        humidity_max = request.args.get("humidity_max", type=float)
        pressure_min = request.args.get("pressure_min", type=float)
        pressure_max = request.args.get("pressure_max", type=float)
        aqi_min = request.args.get("aqi_min", type=float)
        aqi_max = request.args.get("aqi_max", type=float)
        co2_min = request.args.get("co2_min", type=float)
        co2_max = request.args.get("co2_max", type=float)
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        limit = request.args.get("limit", default=1000, type=int)
        export_csv = request.args.get("export_csv", "false").lower() == "true"
        
        # Build SQL query
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
        if pressure_min is not None:
            query_sql += " AND pressure >= ?"
            params.append(pressure_min)
        if pressure_max is not None:
            query_sql += " AND pressure <= ?"
            params.append(pressure_max)
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
        
        # Execute query
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(query_sql, params)
        rows = cursor.fetchall()
        conn.close()
        
        if export_csv:
            # Return as CSV
            import csv
            from io import StringIO
            
            output = StringIO()
            writer = csv.writer(output)
            
            # Write header
            if rows:
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
            
            csv_content = output.getvalue()
            output.close()
            
            return csv_content, 200, {
                'Content-Type': 'text/csv',
                'Content-Disposition': f'attachment; filename=sensor_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            }
        else:
            # Return as JSON
            result = [dict(row) for row in rows]
            return jsonify({
                "count": len(result),
                "records": result
            }), 200
            
    except Exception as e:
        return jsonify({"error": str(e)}), 400


if __name__ == "__main__":
    print("=" * 50)
    print("Air Quality Sensor Server (SQLite)")
    print("=" * 50)
    
    # Initialize database
    init_database()
    
    print(f"\nDatabase file: {DB_FILE}")
    print("Server running on http://0.0.0.0:5020")
    print("\nEndpoints:")
    print("  POST /sensor_data    - Receive sensor data")
    print("  GET  /status         - Check server status")
    print("  GET  /latest         - Get most recent reading")
    print("  GET  /query          - Query with filters")
    print("\nExample query:")
    print("  http://192.168.8.100:5020/query?temp_min=32&temp_max=35&humidity_min=50&humidity_max=80&export_csv=true")
    print("\nPress Ctrl+C to stop")
    print("=" * 50)
    
    # Start server
    app.run(host="0.0.0.0", port=5020, debug=False)
