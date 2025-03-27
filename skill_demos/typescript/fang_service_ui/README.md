# FANG Service UI

## Overview
This is a React+TypeScript web application that interfaces with the `fang_service` FastAPI application.
It allows you to:
- Fetch and display *all* stock data cached on the server.
- Select a specific FANG symbol (FB, AMZN, NFLX, GOOG) from a dropdown to display that symbol’s data only.

## Features
- Simple UI to demonstrate how to interact with the `fang_service` API.
- Basic JSON-format logging to the console (mirroring the server’s style).
- Optional (commented out) Datadog APM integration (Node side) for demonstration.

## Getting Started

1. **Install Dependencies**:
   ```bash
   cd fang_service_ui
   npm install
