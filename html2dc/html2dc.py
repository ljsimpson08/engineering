import asyncio
import os
from pathlib import Path
from bs4 import BeautifulSoup
from html2docx import html2docx
from tempfile import TemporaryDirectory
from urllib.parse import urljoin

from playwright.async_api import async_playwright

# ============================================================================
# CONFIGURATION - Modify these variables
# ============================================================================

# SOURCE: Where to read the HTML from - "Local" or "S3"
HTML_SOURCE = "Local"  # Options: "Local" or "S3"

# DESTINATION: Where to write output - "Local" or "Confluence"
OUTPUT_DESTINATION = "Local"  # Options: "Local" or "Confluence"

# LOCAL SOURCE SETTINGS
LOCAL_HTML_FILE = "input.html"              # Path to HTML file to convert

# S3 SOURCE SETTINGS
S3_BUCKET = "my-bucket-name"                # S3 bucket containing HTML file
S3_HTML_KEY = "reports/report.html"         # S3 key/path to HTML file

# LOCAL DESTINATION SETTINGS
LOCAL_OUTPUT_DOCX = "output.docx"           # Where to save the DOCX locally

# CONFLUENCE DESTINATION SETTINGS
CONFLUENCE_URL = "https://your-domain.atlassian.net"
CONFLUENCE_USERNAME = os.getenv("CONFLUENCE_USER", "your-email@example.com")
CONFLUENCE_API_TOKEN = os.getenv("CONFLUENCE_TOKEN", "your-api-token")
CONFLUENCE_SPACE_KEY = "TEAM"               # Confluence space key
CONFLUENCE_PARENT_PAGE_ID = "123456789"     # Parent page ID (optional, set to None if not needed)
CONFLUENCE_PAGE_TITLE = "Automated Report"  # Title for the Confluence page

# ============================================================================
# END CONFIGURATION
# ============================================================================

INTERACTIVE_SELECTORS = [
    "canvas",
    "svg",
    ".plotly",                # Plotly
    ".js-plotly-plot",        # Plotly alt root
    ".highcharts-container",  # Highcharts
    ".chartjs-render-monitor",# Chart.js canvas
    "[data-chart]",
    "iframe"
]

async def render_and_screenshot(html_path: Path, out_dir: Path):
    """
    Loads the HTML in headless Chromium, screenshots matching selectors,
    returns a dict mapping element ids (assigned) -> screenshot file path.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width":1600,"height":1000})

        # Use file:// URI so relative assets can load.
        uri = html_path.resolve().as_uri()
        await page.goto(uri, wait_until="networkidle")

        # Give charts some time to finish animating/rendering
        await page.wait_for_timeout(1200)

        # Collect elements and screenshot
        screenshots = {}
        idx = 0
        for sel in INTERACTIVE_SELECTORS:
            elements = await page.query_selector_all(sel)
            for el in elements:
                # Skip hidden/tiny elements
                box = await el.bounding_box()
                if not box or box["width"] < 16 or box["height"] < 16:
                    continue

                # Assign a synthetic id we can match in soup
                el_id = await el.get_attribute("id")
                if not el_id:
                    el_id = f"auto-cap-{idx}"
                    await page.evaluate(
                        "(node, _id) => node.setAttribute('id', _id)", el, el_id
                    )

                shot_path = out_dir / f"{el_id}.png"
                await el.screenshot(path=str(shot_path))
                screenshots[el_id] = str(shot_path)
                idx += 1

        await browser.close()
        return screenshots

def replace_interactives_with_imgs(soup: BeautifulSoup, id_to_img: dict):
    """
    Replace interactive nodes by id with <img> tags pointing to captured images.
    """
    for el_id, img_path in id_to_img.items():
        tag = soup.find(id=el_id)
        if tag is None:
            continue
        img = soup.new_tag("img", src=img_path)
        # Try to preserve approximate width via inline style if we have it
        if tag.has_attr("style"):
            img["style"] = tag["style"]
        # Drop the original node; insert the image
        tag.replace_with(img)

def inline_base_href(soup: BeautifulSoup, base: str):
    """
    Resolve <img src>, <link href>, etc. to absolute file paths where possible,
    improving conversion fidelity for local assets.
    """
    for im in soup.find_all("img"):
        src = im.get("src")
        if src and not src.startswith(("http://","https://","data:","file:")):
            im["src"] = urljoin(base, src)
    for link in soup.find_all("link"):
        href = link.get("href")
        if href and not href.startswith(("http://","https://","data:","file:")):
            link["href"] = urljoin(base, href)
    for s in soup.find_all("script"):
        src = s.get("src")
        if src and not src.startswith(("http://","https://","data:","file:")):
            s["src"] = urljoin(base, src)

def convert_html_to_docx(static_html: str, output_docx: Path):
    """Convert HTML to DOCX format."""
    document = html2docx(static_html)
    document.save(str(output_docx))

def download_from_s3(bucket: str, key: str, local_path: Path):
    """Download file from S3 to local path."""
    import boto3
    s3 = boto3.client('s3')
    print(f"📥 Downloading s3://{bucket}/{key}...")
    s3.download_file(bucket, key, str(local_path))
    print(f"✅ Downloaded to {local_path}")

def create_confluence_page(title: str, html_content: str, space_key: str, 
                          parent_id: str = None, screenshots_dir: Path = None):
    """Create a Confluence page with the given HTML content and attach screenshots."""
    from atlassian import Confluence
    
    confluence = Confluence(
        url=CONFLUENCE_URL,
        username=CONFLUENCE_USERNAME,
        password=CONFLUENCE_API_TOKEN,
        cloud=True
    )
    
    print(f"📝 Creating Confluence page: {title}")
    
    # Create the page
    result = confluence.create_page(
        space=space_key,
        title=title,
        body=html_content,
        parent_id=parent_id if parent_id else None,
        representation='storage'
    )
    
    page_id = result['id']
    
    # Attach screenshots if available
    if screenshots_dir and screenshots_dir.exists():
        print(f"📎 Attaching screenshots to Confluence page...")
        for screenshot in screenshots_dir.glob("*.png"):
            confluence.attach_file(
                filename=str(screenshot),
                page_id=page_id,
                title=screenshot.name
            )
            print(f"  ✓ Attached {screenshot.name}")
    
    page_url = f"{CONFLUENCE_URL}/wiki/spaces/{space_key}/pages/{page_id}"
    print(f"✅ Confluence page created: {page_url}")
    return result

async def get_html_source(tmp_dir: Path) -> Path:
    """
    Get the HTML file based on HTML_SOURCE setting.
    Returns the path to the local HTML file.
    """
    if HTML_SOURCE == "Local":
        print(f"📂 Reading HTML from local file: {LOCAL_HTML_FILE}")
        return Path(LOCAL_HTML_FILE)
    
    elif HTML_SOURCE == "S3":
        print(f"☁️  Reading HTML from S3: s3://{S3_BUCKET}/{S3_HTML_KEY}")
        local_html = tmp_dir / "downloaded.html"
        download_from_s3(S3_BUCKET, S3_HTML_KEY, local_html)
        return local_html
    
    else:
        raise ValueError(f"Invalid HTML_SOURCE: {HTML_SOURCE}. Must be 'Local' or 'S3'")

async def write_output(soup: BeautifulSoup, shots_dir: Path):
    """
    Write the processed HTML based on OUTPUT_DESTINATION setting.
    """
    if OUTPUT_DESTINATION == "Local":
        print(f"💾 Writing to local DOCX: {LOCAL_OUTPUT_DOCX}")
        out_docx = Path(LOCAL_OUTPUT_DOCX)
        convert_html_to_docx(str(soup), out_docx)
        print(f"✅ Wrote: {out_docx}")
    
    elif OUTPUT_DESTINATION == "Confluence":
        print(f"☁️  Writing to Confluence space: {CONFLUENCE_SPACE_KEY}")
        html_content = str(soup)
        create_confluence_page(
            title=CONFLUENCE_PAGE_TITLE,
            html_content=html_content,
            space_key=CONFLUENCE_SPACE_KEY,
            parent_id=CONFLUENCE_PARENT_PAGE_ID if CONFLUENCE_PARENT_PAGE_ID else None,
            screenshots_dir=shots_dir
        )
    
    else:
        raise ValueError(f"Invalid OUTPUT_DESTINATION: {OUTPUT_DESTINATION}. Must be 'Local' or 'Confluence'")

async def main():
    """
    Main entry point - processes HTML based on source and destination settings.
    
    Supported combinations:
    - Local → Local: Read local HTML, write DOCX locally
    - Local → Confluence: Read local HTML, create Confluence page
    - S3 → Local: Download from S3, write DOCX locally
    - S3 → Confluence: Download from S3, create Confluence page
    """
    print(f"🚀 Starting HTML processor")
    print(f"   Source: {HTML_SOURCE}")
    print(f"   Destination: {OUTPUT_DESTINATION}")
    print()
    
    with TemporaryDirectory() as td:
        tmp = Path(td)
        
        # Step 1: Get the HTML file
        html_path = await get_html_source(tmp)
        
        # Step 2: Load and process HTML
        raw = html_path.read_text(encoding="utf-8", errors="ignore")
        soup = BeautifulSoup(raw, "lxml")
        
        # Resolve relative asset paths
        inline_base_href(soup, html_path.parent.resolve().as_uri() + "/")
        
        # Step 3: Render & screenshot interactive elements
        shots_dir = tmp / "screenshots"
        shots_dir.mkdir()
        shots = await render_and_screenshot(html_path, shots_dir)
        
        # Step 4: Replace interactive nodes with images
        replace_interactives_with_imgs(soup, shots)
        
        # Step 5: Write output based on destination
        await write_output(soup, shots_dir)
    
    print()
    print("✨ Done!")

if __name__ == "__main__":
    asyncio.run(main())