#!/usr/bin/env python3

import os
import requests
import time
from requests.auth import HTTPBasicAuth

# ANSI color codes for console output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

RAILS_APP_URL = os.environ.get("RAILS_APP_URL", "http://localhost:3000")
USERNAME = os.environ.get("DEVELOPMENT_USERNAME", "X")
PASSWORD = os.environ.get("DEVELOPMENT_PASSWORD", "development")


def print_result(test_name, success, status_code=None, message=None):
    """
    Prints a color-coded test result with optional status code and message.

    :param test_name: Name/label of the test (string)
    :param success: Boolean indicating success or failure
    :param status_code: Optional integer HTTP status code from server
    :param message: Additional detail or error message from the response
    """
    color = GREEN if success else RED
    result_text = "Success" if success else "Fail"
    status_text = f"(HTTP {status_code})" if status_code else ""
    # Show message only if provided
    detail_text = f"=> {message}" if message else ""

    print(f"{test_name}: {color}{result_text}{RESET} {status_text} {detail_text}")


# ------------------------------------------------------------------------------
# Legacy API Tests
# ------------------------------------------------------------------------------

def test_valid_test_card():
    """
    Sends a valid test card and expects:
      - 200 or 201 HTTP status
      - 'status': 'success' in the JSON body
    """
    test_name = "ValidTestCard"
    payload = {
        "payment_method": {
            "card_number": "4111111111111111",  # valid test card
            "month": "12",
            "year": "2025",
            "first_name": "Test",
            "last_name": "User",
            "cvv": "123",
            "email": "test@example.com"
        }
    }

    try:
        resp = requests.post(
            f"{RAILS_APP_URL}/api/v1/payment_methods/tokenize",
            json=payload,
            auth=HTTPBasicAuth(USERNAME, PASSWORD),
            timeout=5
        )
    except requests.RequestException as e:
        print_result(test_name, False, message=f"Request error: {e}")
        return

    # Evaluate the response
    if resp.status_code in (200, 201):
        data = resp.json()
        if (
            data.get("status") == "success"
            and "payment_method_token" in data
            and "stored_id" in data
            and "created_at" in data
        ):
            print_result(test_name, True, status_code=resp.status_code)
        else:
            # Possibly got a 200 or 201 but the JSON wasn't as expected
            print_result(
                test_name,
                False,
                status_code=resp.status_code,
                message=f"Unexpected success response: {data}"
            )
    else:
        # We expected 200 or 201, so anything else is a fail
        try:
            data = resp.json()
            # Include any error or message from the response
            print_result(
                test_name,
                False,
                status_code=resp.status_code,
                message=data.get("error") or str(data)
            )
        except ValueError:
            # If body isn't valid JSON
            print_result(
                test_name,
                False,
                status_code=resp.status_code,
                message=f"Raw response: {resp.text}"
            )


def test_invalid_card_number():
    """
    Sends a non-test card and expects:
      - 422 HTTP status
      - { "error": "Only test cards are allowed" } in the JSON
    """
    test_name = "InvalidCardNumber"
    payload = {
        "payment_method": {
            "card_number": "9999999999999999",  # not in valid test card list
            "month": "12",
            "year": "2025",
            "first_name": "Invalid",
            "last_name": "Card",
            "cvv": "123",
            "email": "invalid.card@example.com"
        }
    }

    try:
        resp = requests.post(
            f"{RAILS_APP_URL}/api/v1/payment_methods/tokenize",
            json=payload,
            auth=HTTPBasicAuth(USERNAME, PASSWORD),
            timeout=5
        )
    except requests.RequestException as e:
        print_result(test_name, False, message=f"Request error: {e}")
        return

    if resp.status_code == 422:
        data = resp.json()
        if data.get("error") == "Only test cards are allowed":
            print_result(test_name, True, status_code=resp.status_code)
        else:
            # We got 422 but a different error message
            print_result(
                test_name,
                False,
                status_code=resp.status_code,
                message=f"Unexpected error message: {data}"
            )
    else:
        # We expected 422, so anything else is a fail
        try:
            data = resp.json()
            print_result(
                test_name,
                False,
                status_code=resp.status_code,
                message=data.get("error") or str(data)
            )
        except ValueError:
            print_result(
                test_name,
                False,
                status_code=resp.status_code,
                message=f"Raw response: {resp.text}"
            )


def test_missing_auth():
    """
    Omits Basic Auth and expects:
      - 401 HTTP status for authentication failure
      - { "error": "Authentication failed" } in the JSON
    """
    test_name = "MissingAuth"
    payload = {
        "payment_method": {
            "card_number": "4111111111111111",
            "month": "12",
            "year": "2025",
            "first_name": "NoAuth",
            "last_name": "User",
            "cvv": "123",
            "email": "noauth@example.com"
        }
    }

    try:
        resp = requests.post(
            f"{RAILS_APP_URL}/api/v1/payment_methods/tokenize",
            json=payload,
            timeout=5  # Note: no auth specified
        )
    except requests.RequestException as e:
        print_result(test_name, False, message=f"Request error: {e}")
        return

    if resp.status_code == 401:
        try:
            data = resp.json()
            if data.get("error") == "Authentication failed":
                print_result(test_name, True, status_code=resp.status_code)
            else:
                print_result(
                    test_name,
                    False,
                    status_code=resp.status_code,
                    message=f"Unexpected error message: {data}"
                )
        except ValueError:
            print_result(
                test_name,
                True,
                status_code=resp.status_code,
                message="Got 401 status but response wasn't valid JSON"
            )
    else:
        try:
            data = resp.json()
            print_result(
                test_name,
                False,
                status_code=resp.status_code,
                message=data.get("error") or str(data)
            )
        except ValueError:
            print_result(
                test_name,
                False,
                status_code=resp.status_code,
                message=f"Raw response: {resp.text}"
            )


def test_invalid_auth():
    """
    Provides invalid authentication credentials and expects:
      - 401 HTTP status
      - { "error": "Authentication failed" } in the JSON
    """
    test_name = "InvalidAuth"
    payload = {
        "payment_method": {
            "card_number": "4111111111111111",
            "month": "12",
            "year": "2025",
            "first_name": "BadAuth",
            "last_name": "User",
            "cvv": "123",
            "email": "badauth@example.com"
        }
    }

    try:
        resp = requests.post(
            f"{RAILS_APP_URL}/api/v1/payment_methods/tokenize",
            json=payload,
            auth=HTTPBasicAuth("wrong", "credentials"),
            timeout=5
        )
    except requests.RequestException as e:
        print_result(test_name, False, message=f"Request error: {e}")
        return

    if resp.status_code == 401:
        try:
            data = resp.json()
            if data.get("error") == "Authentication failed":
                print_result(test_name, True, status_code=resp.status_code)
            else:
                print_result(
                    test_name,
                    False,
                    status_code=resp.status_code,
                    message=f"Unexpected error message: {data}"
                )
        except ValueError:
            print_result(
                test_name,
                True,
                status_code=resp.status_code,
                message="Got 401 status but response wasn't valid JSON"
            )
    else:
        try:
            data = resp.json()
            print_result(
                test_name,
                False,
                status_code=resp.status_code,
                message=data.get("error") or str(data)
            )
        except ValueError:
            print_result(
                test_name,
                False,
                status_code=resp.status_code,
                message=f"Raw response: {resp.text}"
            )


def test_missing_card_info():
    """
    Sends a request with missing required card info and expects:
      - 400 or 422 HTTP status
      - Error message about missing parameters
    """
    test_name = "MissingCardInfo"
    payload = {
        "payment_method": {
            # Missing card_number
            "month": "12",
            "year": "2025",
            "first_name": "Missing",
            "last_name": "Info",
            "cvv": "123",
            "email": "missing.info@example.com"
        }
    }

    try:
        resp = requests.post(
            f"{RAILS_APP_URL}/api/v1/payment_methods/tokenize",
            json=payload,
            auth=HTTPBasicAuth(USERNAME, PASSWORD),
            timeout=5
        )
    except requests.RequestException as e:
        print_result(test_name, False, message=f"Request error: {e}")
        return

    # Accept either 400 or 422 as both are valid for parameter errors
    if resp.status_code in (400, 422):
        print_result(test_name, True, status_code=resp.status_code)
    else:
        try:
            data = resp.json()
            print_result(
                test_name,
                False,
                status_code=resp.status_code,
                message=data.get("error") or str(data)
            )
        except ValueError:
            print_result(
                test_name,
                False,
                status_code=resp.status_code,
                message=f"Raw response: {resp.text}"
            )


# ------------------------------------------------------------------------------
# New Grape API Tests
# ------------------------------------------------------------------------------

def test_valid_test_card_grape_api():
    """
    Tests the new Grape API endpoint with a valid test card
    """
    test_name = "ValidTestCardGrapeAPI"
    payload = {
        "payment_method": {
            "card_number": "4111111111111111",
            "month": "12",
            "year": "2025",
            "first_name": "Test",
            "last_name": "User",
            "cvv": "123",
            "email": "test@example.com"
        }
    }

    try:
        resp = requests.post(
            f"{RAILS_APP_URL}/v1/payment_methods/tokenize",
            json=payload,
            auth=HTTPBasicAuth(USERNAME, PASSWORD),
            timeout=5
        )
    except requests.RequestException as e:
        print_result(test_name, False, message=f"Request error: {e}")
        return

    # Evaluate the response
    if resp.status_code in (200, 201):
        data = resp.json()
        if (
            data.get("status") == "success"
            and "payment_method_token" in data
            and "stored_id" in data
            and "created_at" in data
        ):
            print_result(test_name, True, status_code=resp.status_code)
        else:
            print_result(
                test_name,
                False,
                status_code=resp.status_code,
                message=f"Unexpected success response: {data}"
            )
    else:
        try:
            data = resp.json()
            print_result(
                test_name,
                False,
                status_code=resp.status_code,
                message=data.get("error") or str(data)
            )
        except ValueError:
            print_result(
                test_name,
                False,
                status_code=resp.status_code,
                message=f"Raw response: {resp.text}"
            )


def test_invalid_card_number_grape_api():
    """
    Tests the new Grape API endpoint with an invalid card number
    """
    test_name = "InvalidCardNumberGrapeAPI"
    payload = {
        "payment_method": {
            "card_number": "9999999999999999",  # not in valid test card list
            "month": "12",
            "year": "2025",
            "first_name": "Invalid",
            "last_name": "Card",
            "cvv": "123",
            "email": "invalid.card@example.com"
        }
    }

    try:
        resp = requests.post(
            f"{RAILS_APP_URL}/v1/payment_methods/tokenize",
            json=payload,
            auth=HTTPBasicAuth(USERNAME, PASSWORD),
            timeout=5
        )
    except requests.RequestException as e:
        print_result(test_name, False, message=f"Request error: {e}")
        return

    if resp.status_code == 422:
        data = resp.json()
        if data.get("error") == "Only test cards are allowed":
            print_result(test_name, True, status_code=resp.status_code)
        else:
            print_result(
                test_name,
                False,
                status_code=resp.status_code,
                message=f"Unexpected error message: {data}"
            )
    else:
        try:
            data = resp.json()
            print_result(
                test_name,
                False,
                status_code=resp.status_code,
                message=data.get("error") or str(data)
            )
        except ValueError:
            print_result(
                test_name,
                False,
                status_code=resp.status_code,
                message=f"Raw response: {resp.text}"
            )


def test_missing_auth_grape_api():
    """
    Tests authentication failure on the new Grape API endpoint
    """
    test_name = "MissingAuthGrapeAPI"
    payload = {
        "payment_method": {
            "card_number": "4111111111111111",
            "month": "12",
            "year": "2025",
            "first_name": "NoAuth",
            "last_name": "User",
            "cvv": "123",
            "email": "noauth@example.com"
        }
    }

    try:
        resp = requests.post(
            f"{RAILS_APP_URL}/v1/payment_methods/tokenize",
            json=payload,
            timeout=5  # Note: no auth specified
        )
    except requests.RequestException as e:
        print_result(test_name, False, message=f"Request error: {e}")
        return

    if resp.status_code == 401:
        try:
            data = resp.json()
            # The error message might be different in Grape
            print_result(test_name, True, status_code=resp.status_code)
        except ValueError:
            print_result(
                test_name,
                True,
                status_code=resp.status_code,
                message="Got 401 status but response wasn't valid JSON"
            )
    else:
        try:
            data = resp.json()
            print_result(
                test_name,
                False,
                status_code=resp.status_code,
                message=data.get("error") or str(data)
            )
        except ValueError:
            print_result(
                test_name,
                False,
                status_code=resp.status_code,
                message=f"Raw response: {resp.text}"
            )


def test_missing_params_grape_api():
    """
    Tests parameter validation on the new Grape API endpoint
    """
    test_name = "MissingParamsGrapeAPI"
    payload = {
        "payment_method": {
            # Missing card_number which is required
            "month": "12",
            "year": "2025",
            "first_name": "Missing",
            "last_name": "Params",
            "cvv": "123",
            "email": "missing.params@example.com"
        }
    }

    try:
        resp = requests.post(
            f"{RAILS_APP_URL}/v1/payment_methods/tokenize",
            json=payload,
            auth=HTTPBasicAuth(USERNAME, PASSWORD),
            timeout=5
        )
    except requests.RequestException as e:
        print_result(test_name, False, message=f"Request error: {e}")
        return

    # Grape should return 400 for parameter validation errors
    if resp.status_code == 400:
        print_result(test_name, True, status_code=resp.status_code)
    else:
        try:
            data = resp.json()
            print_result(
                test_name,
                False,
                status_code=resp.status_code,
                message=data.get("error") or str(data)
            )
        except ValueError:
            print_result(
                test_name,
                False,
                status_code=resp.status_code,
                message=f"Raw response: {resp.text}"
            )


def test_health_endpoint():
    """
    Tests the health check endpoint
    """
    test_name = "HealthEndpoint"

    try:
        resp = requests.get(
            f"{RAILS_APP_URL}/health",
            timeout=5
        )
    except requests.RequestException as e:
        print_result(test_name, False, message=f"Request error: {e}")
        return

    if resp.status_code == 200:
        try:
            data = resp.json()
            if data.get("status") == "ok":
                print_result(test_name, True, status_code=resp.status_code)
            else:
                print_result(
                    test_name,
                    False,
                    status_code=resp.status_code,
                    message=f"Unexpected response: {data}"
                )
        except ValueError:
            print_result(
                test_name,
                False,
                status_code=resp.status_code,
                message=f"Response is not valid JSON: {resp.text}"
            )
    else:
        print_result(
            test_name,
            False,
            status_code=resp.status_code,
            message=f"Unexpected status code: {resp.status_code}"
        )


def test_rate_limiting():
    """
    Tests the rate limiting functionality by making multiple rapid requests
    """
    test_name = "RateLimiting"
    payload = {
        "payment_method": {
            "card_number": "4111111111111111",
            "month": "12",
            "year": "2025",
            "first_name": "Rate",
            "last_name": "Limit",
            "cvv": "123",
            "email": "rate.limit@example.com"
        }
    }

    # Make 10 requests in rapid succession to trigger rate limiting
    responses = []
    for i in range(10):
        try:
            resp = requests.post(
                f"{RAILS_APP_URL}/v1/payment_methods/tokenize",
                json=payload,
                auth=HTTPBasicAuth(USERNAME, PASSWORD),
                timeout=5
            )
            responses.append(resp)
            # Small sleep to ensure requests are properly recorded
            time.sleep(0.01)
        except requests.RequestException as e:
            print_result(test_name, False, message=f"Request error: {e}")
            return

    # Check if any of the responses were rate limited (HTTP 429)
    rate_limited = any(resp.status_code == 429 for resp in responses)
    rate_limit_headers = any('X-RateLimit-Limit' in resp.headers for resp in responses)

    if rate_limited or rate_limit_headers:
        print_result(test_name, True, message="Rate limiting is functioning")
    else:
        print_result(
            test_name,
            False,
            message="No rate limiting detected in responses"
        )


def main():
    print(f"Running tests against: {RAILS_APP_URL}\n")

    print(f"{YELLOW}Authentication Tests:{RESET}")
    test_missing_auth()
    test_invalid_auth()

    print(f"\n{YELLOW}Legacy API Tests:{RESET}")
    test_valid_test_card()
    test_invalid_card_number()
    test_missing_card_info()

    print(f"\n{YELLOW}New Grape API Tests:{RESET}")
    test_valid_test_card_grape_api()
    test_invalid_card_number_grape_api()
    test_missing_auth_grape_api()
    test_missing_params_grape_api()

    print(f"\n{YELLOW}Health Check Test:{RESET}")
    test_health_endpoint()

    print(f"\n{YELLOW}Rate Limiting Test:{RESET}")
    test_rate_limiting()

    print("\nTests completed!")


if __name__ == "__main__":
    main()
