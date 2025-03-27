import json
import time
import traceback
import re
import requests
from urllib.parse import urlparse, urljoin, parse_qs
import logging
import os
import socket
import ipaddress

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
# For WebDriver Manager
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("website_security_scan.log", mode='w'),
        logging.StreamHandler()
    ]
)


def create_webdriver(headless=False, user_agent=None):
    """
    Create and return a Chrome WebDriver instance using WebDriver Manager.
    This will automatically download/manage the matching ChromeDriver.
    """
    options = webdriver.ChromeOptions()
    # Capture console logs
    options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
    
    # Optionally run headless
    if headless:
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
    
    # Set user agent if provided; otherwise use a default
    if user_agent:
        options.add_argument(f'user-agent={user_agent}')
    else:
        options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        )
    
    # Use WebDriver Manager without specifying a path
    service = Service(ChromeDriverManager().install())
    
    driver = webdriver.Chrome(service=service, options=options)
    
    return driver


def is_same_domain(base_url, link):
    try:
        base_domain = urlparse(base_url).netloc
        link_domain = urlparse(link).netloc
        return (base_domain == link_domain) or (link_domain == '')
    except Exception as e:
        logging.warning(f"Error checking domain for {link} - {str(e)}")
        return False


def get_all_links(driver, base_url):
    all_links = set()
    try:
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.TAG_NAME, "a")))
    except Exception:
        logging.debug("No <a> tags found within 5 seconds or none present.")
    
    elements = driver.find_elements(By.TAG_NAME, 'a')
    for elem in elements:
        try:
            href = elem.get_attribute('href')
            if href:
                if href.startswith('javascript:'):
                    continue
                if not (href.startswith('http') or href.startswith('/') or href.startswith('#')):
                    continue
                absolute_url = urljoin(base_url, href)
                if is_same_domain(base_url, absolute_url) and absolute_url.startswith('http'):
                    all_links.add(absolute_url)
        except Exception as e:
            logging.warning(f"Error processing link element: {str(e)}")
            logging.debug(traceback.format_exc())
    return all_links


def extract_ips_from_page(driver):
    page_source = driver.page_source
    ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
    ips = re.findall(ip_pattern, page_source)
    
    valid_ips = []
    for ip in ips:
        try:
            ip_obj = ipaddress.IPv4Address(ip)
            if not ip_obj.is_private and not ip_obj.is_loopback and not ip_obj.is_link_local:
                valid_ips.append(ip)
        except ValueError:
            pass
    return valid_ips


def detect_apis(driver, base_url):
    potential_apis = set()
    
    # API patterns
    api_patterns = [
        r'https?://[^"\'\s]+/api/[^"\'\s]+',
        r'https?://api\.[^"\'\s]+',
        r'https?://[^"\'\s]+/v\d+/[^"\'\s]+',
        r'https?://[^"\'\s]+/rest/[^"\'\s]+',
        r'https?://[^"\'\s]+/graphql[^"\'\s]*',
        r'https?://[^"\'\s]+/gql[^"\'\s]*',
        r'https?://[^"\'\s]+/service[^"\'\s]*',
        r'https?://[^"\'\s]+/data[^"\'\s]*'
    ]
    
    # AJAX patterns
    ajax_patterns = [
        r'\.ajax\(\s*{\s*[^}]*url\s*:\s*[\'"]([^\'"]+)[\'"]',
        r'\.get\([\'"]([^\'"]+)[\'"]',
        r'\.post\([\'"]([^\'"]+)[\'"]',
        r'fetch\([\'"]([^\'"]+)[\'"]',
        r'new XMLHttpRequest\([\'"]([^\'"]+)[\'"]'
    ]
    
    # Check script tags
    script_elements = driver.find_elements(By.TAG_NAME, 'script')
    for script in script_elements:
        try:
            script_content = script.get_attribute('innerHTML')
            if script_content:
                for pattern in api_patterns:
                    matches = re.findall(pattern, script_content)
                    for match in matches:
                        clean_url = match.rstrip("',\"\\/();")
                        potential_apis.add(clean_url)
                
                for pattern in ajax_patterns:
                    matches = re.findall(pattern, script_content)
                    for match in matches:
                        if match.startswith('#'):
                            continue
                        absolute_url = urljoin(base_url, match)
                        potential_apis.add(absolute_url)
        except Exception as e:
            logging.debug(f"Error parsing script content: {str(e)}")
    
    # Check form actions
    forms = driver.find_elements(By.TAG_NAME, 'form')
    for form in forms:
        try:
            action = form.get_attribute('action')
            if action and ('api' in action.lower() or '/v' in action.lower()):
                absolute_url = urljoin(base_url, action)
                potential_apis.add(absolute_url)
        except Exception as e:
            logging.debug(f"Error checking form action: {str(e)}")
    
    # Check data attributes
    elements_with_data = driver.find_elements(By.CSS_SELECTOR, '[data-url], [data-api], [data-endpoint]')
    for elem in elements_with_data:
        for attr in ['data-url', 'data-api', 'data-endpoint']:
            try:
                value = elem.get_attribute(attr)
                if value and ('api' in value.lower() or '/v' in value.lower()):
                    absolute_url = urljoin(base_url, value)
                    potential_apis.add(absolute_url)
            except Exception as e:
                logging.debug(f"Error checking data attribute: {str(e)}")
    
    return [api for api in potential_apis if api.startswith('http')]


def get_service_name(port):
    services = {
        21: "FTP",
        22: "SSH",
        23: "Telnet",
        25: "SMTP",
        80: "HTTP",
        443: "HTTPS",
        445: "SMB",
        3306: "MySQL",
        3389: "RDP",
        5432: "PostgreSQL",
        8080: "HTTP-Alt",
        8443: "HTTPS-Alt"
    }
    return services.get(port, "Unknown")


def test_ip_security(ip, session=None):
    if session is None:
        session = requests.Session()
    
    result = {
        'ip': ip,
        'open_ports': [],
        'security_findings': [],
        'hostname': None
    }
    
    # Try resolving hostname
    try:
        result['hostname'] = socket.gethostbyaddr(ip)[0]
    except socket.herror:
        result['hostname'] = "Unable to resolve"
    
    common_ports = [21, 22, 23, 25, 80, 443, 445, 3306, 3389, 5432, 8080, 8443]
    for port in common_ports:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            connection = s.connect_ex((ip, port))
            if connection == 0:
                service = get_service_name(port)
                result['open_ports'].append({'port': port, 'service': service})
                if port in [21, 23]:  # FTP, Telnet
                    result['security_findings'].append({
                        'type': 'Insecure Protocol',
                        'severity': 'High',
                        'description': f'Potentially insecure {service} service exposed',
                        'details': f'Port {port} is open'
                    })
                
                if port in [80, 443, 8080, 8443]:
                    protocol = "https" if port in [443, 8443] else "http"
                    target_url = f"{protocol}://{ip}:{port}"
                    try:
                        resp = session.get(target_url, timeout=3)
                        server = resp.headers.get('Server')
                        if server:
                            result['security_findings'].append({
                                'type': 'Information Disclosure',
                                'severity': 'Low',
                                'description': 'Web server information disclosed',
                                'details': f'Server header: {server}'
                            })
                    except:
                        pass
            s.close()
        except socket.error:
            continue
    return result


def parse_console_logs(driver):
    log_entries = driver.get_log('browser')
    parsed_logs = []
    for entry in log_entries:
        level = entry.get('level')
        message = entry.get('message')
        if level in ['SEVERE', 'WARNING']:
            parsed_logs.append({
                'Error Type': level,
                'Error Message': message
            })
    return parsed_logs


def security_test_api_endpoint(url, session=None, extra_headers=None):
    if session is None:
        session = requests.Session()
    
    default_headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        ),
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9'
    }
    if extra_headers:
        default_headers.update(extra_headers)
    
    result = {
        'url': url,
        'methods_tested': {},
        'accessible': False,
        'auth_required': False,
        'content_type': None,
        'response_size': 0,
        'security_findings': [],
        'notes': []
    }
    
    parsed_url = urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
    query_params = parse_qs(parsed_url.query)
    
    methods = ['GET', 'POST', 'HEAD', 'OPTIONS']
    for method in methods:
        try:
            if method == 'GET':
                resp = session.get(url, headers=default_headers, timeout=5)
            elif method == 'POST':
                resp = session.post(url, headers=default_headers, timeout=5, data={})
            elif method == 'HEAD':
                resp = session.head(url, headers=default_headers, timeout=5)
            elif method == 'OPTIONS':
                resp = session.options(url, headers=default_headers, timeout=5)
            
            status_code = resp.status_code
            success = 200 <= status_code < 300
            
            result['methods_tested'][method] = {
                'status_code': status_code,
                'success': success
            }
            
            if success:
                result['accessible'] = True
                content_type = resp.headers.get('Content-Type', '')
                result['content_type'] = content_type
                result['response_size'] = len(resp.content)
                
                # Check for sensitive headers
                sensitive_headers = ['server', 'x-powered-by', 'x-aspnet-version', 'x-aspnetmvc-version']
                exposed_headers = [
                    f"{h}: {resp.headers[h]}" for h in sensitive_headers if h in resp.headers
                ]
                if exposed_headers:
                    result['security_findings'].append({
                        'type': 'Information Disclosure',
                        'severity': 'Low',
                        'description': 'Server exposing potentially sensitive headers',
                        'details': exposed_headers
                    })
                
                # Check CORS if OPTIONS
                if method == 'OPTIONS':
                    if 'Access-Control-Allow-Origin' in resp.headers:
                        if resp.headers['Access-Control-Allow-Origin'] == '*':
                            result['security_findings'].append({
                                'type': 'CORS Misconfiguration',
                                'severity': 'Medium',
                                'description': 'API endpoint allows requests from any origin',
                                'details': 'Access-Control-Allow-Origin: *'
                            })
                
                # If JSON, look for sensitive data
                if 'application/json' in content_type:
                    try:
                        json_data = resp.json()
                        if isinstance(json_data, dict):
                            result['sample_structure'] = list(json_data.keys())[:10]
                        elif isinstance(json_data, list) and len(json_data) > 0:
                            if isinstance(json_data[0], dict):
                                result['sample_structure'] = list(json_data[0].keys())[:10]
                        
                        json_str = json.dumps(json_data) if json_data else ""
                        patterns = {
                            'email': r'[\w\.-]+@[\w\.-]+\.\w+',
                            'credit_card': r'\b(?:\d{4}[- ]?){3}\d{4}\b',
                            'api_key': r'(?i)(api[_-]?key|apikey|access[_-]?key|auth[_-]?key)["\':\s]*([^\s,\'"]+)',
                            'token': r'(?i)(token|jwt|bearer)["\':\s]*([^\s,\'"]+)',
                            'password': r'(?i)(password|passwd|pwd)["\':\s]*([^\s,\'"]+)',
                            'ssn': r'\b\d{3}-\d{2}-\d{4}\b'
                        }
                        for data_type, pattern in patterns.items():
                            matches = re.findall(pattern, json_str)
                            if matches:
                                result['security_findings'].append({
                                    'type': 'Sensitive Data Exposure',
                                    'severity': 'High',
                                    'description': f'Potential {data_type} exposed in API response',
                                    'details': f'Found {len(matches)} potential matches'
                                })
                    except Exception as e:
                        logging.debug(f"Error parsing JSON response: {str(e)}")
            
            if status_code in [401, 403]:
                result['auth_required'] = True
                result['notes'].append(f"{method} request requires authentication")
                
        except requests.exceptions.Timeout:
            result['methods_tested'][method] = {'status_code': 'Timeout', 'success': False}
            result['notes'].append(f"{method} request timed out")
        except requests.exceptions.RequestException as e:
            result['methods_tested'][method] = {'status_code': 'Error', 'success': False}
            result['notes'].append(f"{method} request failed: {str(e)}")
    
    # Extra checks if accessible
    if result['accessible']:
        # --- SQL Injection ---
        if query_params:
            sql_payloads = [
                "'",
                "' OR '1'='1",
                "1' OR '1'='1",
                "' OR 1=1--",
                "; DROP TABLE users;--"
            ]
            for param in query_params:
                for payload in sql_payloads:
                    modified_params = query_params.copy()
                    modified_params[param] = [payload]
                    query_items = []
                    for k, v in modified_params.items():
                        for item in v:
                            query_items.append(f"{k}={item}")
                    modified_url = f"{base_url}?{'&'.join(query_items)}"
                    try:
                        inj_resp = session.get(modified_url, headers=default_headers, timeout=5)
                        text_lower = inj_resp.text.lower()
                        sql_error_patterns = [
                            "sql syntax", "ora-", "mysql", "sqlite", "sqlstate",
                            "syntax error", "unclosed quotation mark", "unterminated string"
                        ]
                        for pattern in sql_error_patterns:
                            if pattern in text_lower:
                                result['security_findings'].append({
                                    'type': 'SQL Injection',
                                    'severity': 'Critical',
                                    'description': f'Potential SQL injection (param: {param})',
                                    'details': f'Payload: {payload}, Found pattern: {pattern}'
                                })
                                break
                    except Exception as e:
                        logging.debug(f"Error during SQL injection test: {str(e)}")
        
        # --- Path Traversal ---
        path_traversal_payloads = [
            "../", "../../", "../../../etc/passwd",
            "../../../windows/win.ini", "..%2f..%2f"
        ]
        for payload in path_traversal_payloads:
            try:
                path_parts = parsed_url.path.rstrip('/').split('/')
                if len(path_parts) > 1:
                    modified_path = '/'.join(path_parts[:-1]) + '/' + payload
                    traversal_url = f"{parsed_url.scheme}://{parsed_url.netloc}{modified_path}"
                    trav_resp = session.get(traversal_url, headers=default_headers, timeout=5)
                    if trav_resp.status_code == 200:
                        if "root:" in trav_resp.text or "[fonts]" in trav_resp.text:
                            result['security_findings'].append({
                                'type': 'Path Traversal',
                                'severity': 'Critical',
                                'description': 'Potential path traversal vulnerability',
                                'details': f'Payload: {payload}, URL: {traversal_url}'
                            })
                            break
            except Exception as e:
                logging.debug(f"Error during path traversal test: {str(e)}")
        
        # --- Missing Rate Limiting ---
        if 'GET' in result['methods_tested'] and result['methods_tested']['GET']['success']:
            try:
                for _ in range(10):
                    resp = session.get(url, headers=default_headers, timeout=2)
                if resp.status_code == 200:
                    result['security_findings'].append({
                        'type': 'Missing Rate Limiting',
                        'severity': 'Medium',
                        'description': 'Endpoint may lack rate limiting',
                        'details': 'Sent 10 rapid requests without throttling'
                    })
            except requests.exceptions.RequestException as e:
                if "429" in str(e) or "Too Many Requests" in str(e):
                    result['notes'].append("Rate limiting appears to be in place.")
                else:
                    logging.debug(f"Error during rate limiting test: {str(e)}")
    
    return result


def crawl_and_test_website(start_url, max_pages=50, headless=False, wait_time=3):
    driver = create_webdriver(headless=headless)
    session = requests.Session()
    
    to_visit = [start_url]
    visited = set()
    
    console_results = []
    total_by_type = {}
    
    detected_apis = set()
    detected_ips = set()
    api_test_results = []
    ip_test_results = []
    
    session_info = {
        "start_url": start_url,
        "headless": headless,
        "wait_time": wait_time,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "scan_type": "Console Errors and Basic Security Testing"
    }
    
    logging.info(f"Starting crawl and security scan at: {start_url} (Headless: {headless}, Wait: {wait_time}s)")
    
    # Main Crawl Loop
    while to_visit and len(visited) < max_pages:
        url = to_visit.pop(0)
        if url in visited:
            continue
        
        visited.add(url)
        logging.info(f"Visiting page ({len(visited)} of {max_pages} max): {url}")
        
        try:
            driver.get(url)
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            time.sleep(wait_time)  # small additional wait if needed
            
            console_logs = parse_console_logs(driver)
            if console_logs:
                logging.info(f"Found {len(console_logs)} console warnings/errors on this page.")
                console_results.append({"Page": url, "Console Messages": console_logs})
                for entry in console_logs:
                    etype = entry['Error Type']
                    total_by_type[etype] = total_by_type.get(etype, 0) + 1
            else:
                logging.info("No console warnings/errors found on this page.")
            
            page_apis = detect_apis(driver, url)
            if page_apis:
                logging.info(f"Found {len(page_apis)} potential API endpoints on this page.")
                detected_apis.update(page_apis)
            
            page_ips = extract_ips_from_page(driver)
            if page_ips:
                logging.info(f"Found {len(page_ips)} public IP addresses on this page.")
                detected_ips.update(page_ips)
            
            page_links = get_all_links(driver, url)
            logging.info(f"Found {len(page_links)} links on this page.")
            for link in page_links:
                if link not in visited and link not in to_visit:
                    to_visit.append(link)
                    
        except Exception as e:
            logging.error(f"Error processing page {url} - {str(e)}")
            logging.debug(traceback.format_exc())
            continue
    
    driver.quit()
    
    # Test all detected APIs
    if detected_apis:
        logging.info(f"Starting security testing on {len(detected_apis)} unique API endpoints...")
        for api_url in detected_apis:
            logging.info(f"Testing API endpoint: {api_url}")
            try:
                test_result = security_test_api_endpoint(api_url, session=session)
                api_test_results.append(test_result)
                if test_result['accessible']:
                    logging.info(f"API {api_url} is accessible.")
                    if test_result['security_findings']:
                        logging.warning(f"Found {len(test_result['security_findings'])} security issues for {api_url}")
                        for finding in test_result['security_findings']:
                            logging.warning(f"  - {finding['severity']} severity: {finding['type']}")
                else:
                    logging.info(f"API endpoint {api_url} is not accessible (4xx/5xx).")
            except Exception as e:
                logging.error(f"Error testing API endpoint {api_url}: {str(e)}")
                logging.debug(traceback.format_exc())
    
    # Test all detected IP addresses
    if detected_ips:
        logging.info(f"Starting security testing on {len(detected_ips)} unique IP addresses...")
        for ip in detected_ips:
            logging.info(f"Testing IP address: {ip}")
            try:
                test_result = test_ip_security(ip, session=session)
                ip_test_results.append(test_result)
                if test_result['open_ports']:
                    logging.info(f"IP {ip} has {len(test_result['open_ports'])} open ports.")
                    for port_info in test_result['open_ports']:
                        logging.info(f"  - Port {port_info['port']} ({port_info['service']}) is open.")
                    
                    if test_result['security_findings']:
                        logging.warning(f"Found {len(test_result['security_findings'])} security issues for IP {ip}.")
                        for finding in test_result['security_findings']:
                            logging.warning(f"  - {finding['severity']} severity: {finding['type']}")
                else:
                    logging.info(f"No open ports found on IP address {ip}.")
            except Exception as e:
                logging.error(f"Error testing IP address {ip}: {str(e)}")
                logging.debug(traceback.format_exc())
    
    # Compile final results
    final_results = {
        "session_info": session_info,
        "console_errors": console_results,
        "console_error_summary": total_by_type,
        "api_test_results": api_test_results,
        "ip_test_results": ip_test_results
    }
    
    with open("scan_results.json", "w", encoding="utf-8") as f:
        json.dump(final_results, f, indent=4)
    
    logging.info("Security scan complete. Results saved to scan_results.json.")
    return final_results


# =========================
#            MAIN
# =========================
if __name__ == "__main__":
    target_url = "https://www.rxhistories.com/"
    max_pages_to_crawl = 100
    run_headless = True
    page_wait_time = 10
    
    results = crawl_and_test_website(
        start_url=target_url,
        max_pages=max_pages_to_crawl,
        headless=run_headless,
        wait_time=page_wait_time
    )
    
    print("\n----- SCAN SUMMARY -----")
    print(f"Start URL: {results['session_info']['start_url']}")
    print(f"Timestamp: {results['session_info']['timestamp']}")
    print(f"Console error counts by type: {results['console_error_summary']}")
    print("Detailed results have been saved to scan_results.json.")