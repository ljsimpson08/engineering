package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"math/rand"
	"net/http"
	"net/url"
	"time"
)

// This struct matches the JSON response from /getStock
type StockResponse struct {
	Symbol    string            `json:"symbol"`
	Timestamp string            `json:"timestamp"`
	Data      map[string]string `json:"data"`
}

// This struct matches the JSON response from /availableSymbols
type SymbolsResponse struct {
	AvailableSymbols []string `json:"available_symbols"`
	Message          string   `json:"message,omitempty"`
}

// This struct matches the error details from a non-200 response
type ErrorResponse struct {
	Message          string   `json:"message"`
	AvailableSymbols []string `json:"available_symbols,omitempty"`
	AvailableDates   []string `json:"available_dates,omitempty"`
	AvailableHours   []int    `json:"available_hours,omitempty"`
}

func main() {
	// 1) Adjust these as needed
	apiKey := "8f4b9e7d1c6a2305f8e9d7b6c5a4e3f2d1c0b9a8f7e6d5c4b3a2918f7e6d5c4" // Must match SERVICE_API_KEY
	baseURL := "http://localhost:8000/api"                                      // Updated to use the API prefix
	fangSymbols := []string{"FB", "AMZN", "NFLX", "GOOG"}

	// 2) Seed random number generator
	rand.Seed(time.Now().UnixNano())

	// First, check which symbols have data in the database
	availableSymbols, err := getAvailableSymbols(baseURL, apiKey)
	if err != nil {
		fmt.Printf("Error fetching available symbols: %v\n", err)
	} else {
		fmt.Printf("Available symbols: %v\n\n", availableSymbols)

		// If we have available symbols, use those instead of the default FANG list
		if len(availableSymbols) > 0 {
			fangSymbols = availableSymbols
		}
	}

	// 3) For each symbol, pick a random time in the last 72 hours
	for _, symbol := range fangSymbols {
		// randomHours in [0..72)
		randomHours := rand.Intn(72)

		// Now minus randomHours
		randomTime := time.Now().UTC().Add(-time.Duration(randomHours) * time.Hour)

		dateParam := randomTime.Format("2006-01-02")
		hourParam := randomTime.Hour()

		// 4) Make the request to get stock data
		fmt.Printf("=== %s Query ===\n", symbol)
		fmt.Printf("Random time: %s %02d:00:00\n", dateParam, hourParam)

		err := queryStockData(baseURL, apiKey, symbol, dateParam, hourParam)
		if err != nil {
			fmt.Printf("Error querying stock data: %v\n\n", err)
		}
	}

	// 5) Also test the /allData endpoint
	fmt.Println("\n=== Testing /allData endpoint ===")
	err = queryAllData(baseURL, apiKey)
	if err != nil {
		fmt.Printf("Error querying all data: %v\n", err)
	}

	fmt.Println("\nAll queries complete.")
}

// Helper function to get available symbols
func getAvailableSymbols(baseURL string, apiKey string) ([]string, error) {
	symbolsURL := fmt.Sprintf("%s/availableSymbols", baseURL)

	client := &http.Client{}
	req, err := http.NewRequest("GET", symbolsURL, nil)
	if err != nil {
		return nil, fmt.Errorf("error creating request: %v", err)
	}
	req.Header.Set("x-api-key", apiKey)

	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("error making request: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		body, _ := ioutil.ReadAll(resp.Body)
		return nil, fmt.Errorf("request returned status %d: %s", resp.StatusCode, string(body))
	}

	var symbolsResp SymbolsResponse
	err = json.NewDecoder(resp.Body).Decode(&symbolsResp)
	if err != nil {
		return nil, fmt.Errorf("error decoding JSON: %v", err)
	}

	return symbolsResp.AvailableSymbols, nil
}

// Helper function to query stock data
func queryStockData(baseURL string, apiKey string, symbol string, date string, hour int) error {
	// Construct the request URL
	reqURL, err := url.Parse(fmt.Sprintf("%s/getStock", baseURL))
	if err != nil {
		return fmt.Errorf("error parsing base URL: %v", err)
	}

	query := reqURL.Query()
	query.Set("symbol", symbol)
	query.Set("date", date)
	query.Set("hour", fmt.Sprintf("%d", hour))
	reqURL.RawQuery = query.Encode()

	// Make the GET request
	client := &http.Client{}
	req, err := http.NewRequest("GET", reqURL.String(), nil)
	if err != nil {
		return fmt.Errorf("error creating request: %v", err)
	}
	req.Header.Set("x-api-key", apiKey)

	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("error making request: %v", err)
	}
	defer resp.Body.Close()

	// Read the response body
	body, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		return fmt.Errorf("error reading response body: %v", err)
	}

	// Check status code
	if resp.StatusCode != 200 {
		var errorResp ErrorResponse
		err = json.Unmarshal(body, &errorResp)
		if err != nil {
			return fmt.Errorf("status %d: %s", resp.StatusCode, string(body))
		}

		fmt.Printf("Request failed with status %d\n", resp.StatusCode)
		fmt.Printf("Error message: %s\n", errorResp.Message)

		if len(errorResp.AvailableDates) > 0 {
			fmt.Printf("Available dates: %v\n", errorResp.AvailableDates)
		}

		if len(errorResp.AvailableHours) > 0 {
			fmt.Printf("Available hours: %v\n", errorResp.AvailableHours)
		}

		return nil
	}

	// Parse the JSON response
	var stockResp StockResponse
	err = json.Unmarshal(body, &stockResp)
	if err != nil {
		return fmt.Errorf("error decoding JSON: %v", err)
	}

	// Print results
	fmt.Printf("Response Symbol: %s\n", stockResp.Symbol)
	fmt.Printf("Response Timestamp: %s\n", stockResp.Timestamp)
	fmt.Printf("Data: %v\n", stockResp.Data)

	return nil
}

// Helper function to query all data
func queryAllData(baseURL string, apiKey string) error {
	allDataURL := fmt.Sprintf("%s/allData", baseURL)

	client := &http.Client{}
	req, err := http.NewRequest("GET", allDataURL, nil)
	if err != nil {
		return fmt.Errorf("error creating request: %v", err)
	}
	req.Header.Set("x-api-key", apiKey)

	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("error making request: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		body, _ := ioutil.ReadAll(resp.Body)
		return fmt.Errorf("request returned status %d: %s", resp.StatusCode, string(body))
	}

	// Read the response but don't attempt to parse the whole thing
	// as it could be very large
	body, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		return fmt.Errorf("error reading response body: %v", err)
	}

	// Check if it's an error message with special "message" field
	var errorCheck map[string]interface{}
	err = json.Unmarshal(body, &errorCheck)
	if err != nil {
		return fmt.Errorf("error parsing JSON response: %v", err)
	}

	if message, ok := errorCheck["message"]; ok {
		fmt.Printf("Received message instead of data: %v\n", message)
		if reason, ok := errorCheck["reason"]; ok {
			fmt.Printf("Reason: %v\n", reason)
		}
		return nil
	}

	// Just count how many symbols and data points we got
	symbolCount := len(errorCheck)
	totalDataPoints := 0

	for symbol, data := range errorCheck {
		if dataMap, ok := data.(map[string]interface{}); ok {
			dataPoints := len(dataMap)
			totalDataPoints += dataPoints
			fmt.Printf("Symbol %s: %d data points\n", symbol, dataPoints)
		}
	}

	fmt.Printf("Total: %d symbols, %d data points\n", symbolCount, totalDataPoints)

	return nil
}
