package main

import (
    "encoding/json"
    "fmt"
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

func main() {
    // 1) Adjust these as needed
    apiKey := "8f4b9e7d1c6a2305f8e9d7b6c5a4e3f2d1c0b9a8f7e6d5c4b3a2918f7e6d5c4" // Must match x-api-key used by your FANG service
    baseURL := "http://localhost:8000/getStock"
    fangSymbols := []string{"FB", "AMZN", "NFLX", "GOOG"}

    // 2) Seed random number generator
    rand.Seed(time.Now().UnixNano())

    // 3) For each FANG symbol, pick a random time in the last 72 hours
    for _, symbol := range fangSymbols {
        // randomHours in [0..72)
        randomHours := rand.Intn(72)

        // Now minus randomHours
        randomTime := time.Now().UTC().Add(-time.Duration(randomHours) * time.Hour)

        dateParam := randomTime.Format("2006-01-02")
        hourParam := randomTime.Hour()

        // 4) Construct the request
        reqURL, err := url.Parse(baseURL)
        if err != nil {
            fmt.Printf("Error parsing base URL: %v\n", err)
            continue
        }
        query := reqURL.Query()
        query.Set("symbol", symbol)
        query.Set("date", dateParam)
        query.Set("hour", fmt.Sprintf("%d", hourParam))
        reqURL.RawQuery = query.Encode()

        // 5) Make the GET request
        client := &http.Client{}
        req, err := http.NewRequest("GET", reqURL.String(), nil)
        if err != nil {
            fmt.Printf("Error creating request: %v\n", err)
            continue
        }

        // Set the x-api-key header
        req.Header.Set("x-api-key", apiKey)

        resp, err := client.Do(req)
        if err != nil {
            fmt.Printf("Error making request to %s: %v\n", reqURL.String(), err)
            continue
        }
        defer resp.Body.Close()

        // 6) Check status code
        if resp.StatusCode != 200 {
            fmt.Printf("Request for %s (date=%s hour=%d) returned status %d\n",
                symbol, dateParam, hourParam, resp.StatusCode)
            continue
        }

        // 7) Parse JSON response
        var stockResp StockResponse
        err = json.NewDecoder(resp.Body).Decode(&stockResp)
        if err != nil {
            fmt.Printf("Error decoding JSON for %s: %v\n", symbol, err)
            continue
        }

        // 8) Print results
        fmt.Printf("=== %s Query ===\n", symbol)
        fmt.Printf("Random time: %s %02d:00:00\n", dateParam, hourParam)
        fmt.Printf("Response Symbol: %s\n", stockResp.Symbol)
        fmt.Printf("Response Timestamp: %s\n", stockResp.Timestamp)
        fmt.Printf("Data: %v\n\n", stockResp.Data)
    }

    fmt.Println("All queries complete.")
}
