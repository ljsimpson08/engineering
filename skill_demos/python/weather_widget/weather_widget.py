import requests

# --- CONFIGURATION ---
API_KEY = 'XXXXXXXXXXXXXXXXX'  # Replace with your OpenWeatherMap API key
ZIPCODE = "90210"         # Change to the ZIP code you want to test
COUNTRY_CODE = "us"       # Adjust if needed, e.g., 'us' for United States
BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

def main():
    # Construct request parameters
    params = {
        "zip": f"{ZIPCODE},{COUNTRY_CODE}",
        "appid": API_KEY,
        "units": "imperial"  # Default to imperial (Fahrenheit)
    }
    
    # Send GET request
    response = requests.get(BASE_URL, params=params)
    
    # Handle response
    if response.status_code == 200:
        data = response.json()
        print("Request Successful!")
        
        # Extract some basic info
        city_name = data.get("name", "N/A")
        main_data = data.get("main", {})
        temperature = main_data.get("temp", "N/A")
        weather_info = data.get("weather", [])
        weather_description = weather_info[0].get("description", "N/A") if weather_info else "N/A"
        
        # Print the results
        print(f"City: {city_name}")
        print(f"Temperature (F): {temperature}")
        print(f"Weather Condition: {weather_description}")
    else:
        print(f"Error: {response.status_code}")
        print("Message:", response.text)

if __name__ == "__main__":
    main()
