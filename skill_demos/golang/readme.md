# test_fang - Go Script for Testing FANG Stock API

This Go script queries a FastAPI endpoint (`/getStock`) that returns intraday stock data for "FANG" companies (Facebook (Meta), Amazon, Netflix, Google). Specifically, it:

- Picks a random date/time within the last 72 hours for each symbol (FB, AMZN, NFLX, GOOG).
- Makes a GET request with `?symbol=SYMBOL&date=YYYY-MM-DD&hour=HH`.
- Sends the required `x-api-key` header to authenticate with the API.
- Prints out the returned JSON data or an error message.

## Prerequisites

- **Go** (1.18 or later recommended).
  - Download from https://go.dev/dl or use your system's package manager.
- A running instance of your FANG Stock Data Service (FastAPI) listening on port 8000 (or whatever is specified in the script).
- A valid API key for your FANG service.

## Installation

### Install Go
Verify via:

```bash
go version
```

You should see something like `go version go1.19.7 darwin/amd64` or similar.

### Clone or copy this script (test_fang.go) to a folder of your choice:

```bash
git clone <your-repo-containing-test_fang.go>
cd <folder-with-test_fang.go>
```

Or just manually download/copy `test_fang.go`.

### Adjust the script:

In `test_fang.go`, update:

```go
apiKey  := "YOUR_SERVICE_API_KEY"
baseURL := "http://localhost:8000/getStock"
```

Replace `"YOUR_SERVICE_API_KEY"` with the real service API key your FANG service requires.

If your API is running on a different address/port, change `baseURL` accordingly.

## Usage

### Run directly:

```bash
go run test_fang.go
```

This compiles the script and runs it immediately. You should see four requests (one for each symbol), printing the results.

### Build an executable:

```bash
go build test_fang.go
```

This produces a binary named `test_fang` (or `test_fang.exe` on Windows).

Then run:

```bash
./test_fang
```

You can commit that executable to version control if needed, or share it with someone who has the same OS/architecture.

## Script Behavior

### Random Hours in [0..72)
For each FANG symbol, the script picks an integer from 0 to 71. That many hours are subtracted from the current UTC time to form the date/hour request parameters.

### API Key
The script sets the `x-api-key` header to `apiKey` (which must match what your FANG service expects).

### Output
For each symbol, the script prints:

- The random date/time used in the request.
- The JSON response fields (symbol, timestamp, data) if successful.
- An error message if the request fails or if the status code is not 200 OK.

Below is a sample console output you might see:

```
=== FB Query ===
Random time: 2023-07-25 10:00:00
Response Symbol: FB
Response Timestamp: 2023-07-25 10:00:00
Data: map[1. open:305.10 2. high:307.55 3. low:303.65 4. close:306.22 5. volume:1054467]

=== AMZN Query ===
Random time: 2023-07-25 02:00:00
Response Symbol: AMZN
Response Timestamp: 2023-07-25 02:00:00
Data: map[1. open:116.41 2. high:117.31 3. low:115.49 4. close:116.84 5. volume:3385128]

...

All queries complete.
```

## Troubleshooting

- **"connection refused" or timeouts**: Check that your FANG service is actually running at localhost:8000 and that your firewall settings allow connections.
- **Status code 401**: The API key is invalid or missing. Update `apiKey`.
- **Status code 404**: The chosen date/hour is not found in the service's data. This can happen if your FANG data is missing that timestamp or the service is not caching for that specific hour.

That's it! Enjoy using `test_fang.go` to quickly verify your FANG Stock Data Service's `/getStock` endpoint.