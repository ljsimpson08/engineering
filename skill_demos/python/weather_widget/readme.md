# Weather Widget

**Filename:** `weather_widget.py`  
**Description:**  
A simple script to test the OpenWeatherMap API. It fetches current weather based on ZIP code and country code, then prints the temperature and weather conditions to the console.

## Features

- **OpenWeatherMap Integration:** Demonstrates a GET request to the OWM API using a provided API key.
- **JSON Parsing:** Extracts city name, temperature, and weather description from the response.
- **Status Handling:** Prints an error message if the response code is not `200`.

## Requirements

- Python 3.x
- `requests` library

## Installation

```bash
pip install requests
Usage
Replace API_KEY with your OpenWeatherMap API key.

Set ZIPCODE and COUNTRY_CODE to your desired location.

Run the script:

bash
Copy
Edit
python weather_widget.py
Check the console for weather info.

Notes
By default, the script uses "imperial" (Fahrenheit). Change "units" to "metric" if you need Celsius.

The request URL is structured as:

bash
Copy
Edit
https://api.openweathermap.org/data/2.5/weather?zip=ZIPCODE,COUNTRY_CODE&appid=API_KEY&units=imperial
Copy
Edit
