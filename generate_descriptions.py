import json
import requests
from bs4 import BeautifulSoup
from openai import OpenAI  # Import the new OpenAI client
import logging
import time
from dotenv import load_dotenv
import os  # Import os to access environment variables

load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Initialize the OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def read_urls_from_file(file_path):
    """Read URLs from a text file, one URL per line."""
    try:
        with open(file_path, 'r') as file:
            urls = [line.strip() for line in file if line.strip()]
        logger.info(f"Successfully read {len(urls)} URLs from {file_path}")
        return urls
    except Exception as e:
        logger.error(f"Error reading URLs from {file_path}: {e}")
        return []

def fetch_page_content(url):
    """Helper function to fetch the content of a single page."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    cookies = {
        "example_cookie": "example_value"  # Replace with actual cookies if needed
    }
    try:
        response = requests.get(url, headers=headers, cookies=cookies, timeout=10)
        response.raise_for_status()  # Raise an error for bad status codes
        return response.text
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching {url}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Response content: {e.response.text}")  # Log the response content
        return ""

def extract_text_from_html(html_content):
    """Helper function to extract and clean text from HTML."""
    soup = BeautifulSoup(html_content, "html.parser")
    # Remove script and style elements
    for script_or_style in soup(["script", "style"]):
        script_or_style.decompose()
    # Get text and clean it
    text = soup.get_text(separator=" ", strip=True)
    return text

def scrape_page(url):
    """Scrape the content of a webpage."""
    try:
        logger.info(f"Scraping {url}...")
        html_content = fetch_page_content(url)
        if html_content:
            text = extract_text_from_html(html_content)
            logger.debug(f"Scraped content (first 500 chars): {text[:500]}")
            return text[:500]  # Return the first 500 characters as a summary
        else:
            logger.warning(f"No content fetched for {url}")
            return ""
    except Exception as e:
        logger.error(f"Error scraping {url}: {e}")
        return ""

def generate_description(text):
    """Generate a one-sentence description using OpenAI."""
    try:
        logger.info("Generating description using OpenAI...")
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",  # Use the appropriate model
            messages=[
                {"role": "system", "content": "Summarize the following content in one sentence:"},
                {"role": "user", "content": text}
            ],
            max_tokens=50
        )
        description = response.choices[0].message.content.strip()
        logger.debug(f"Generated description: {description}")
        return description
    except Exception as e:
        logger.error(f"Error generating description: {e}")
        return ""

def process_urls(urls):
    """Process each URL, scrape content, and generate descriptions."""
    results = []
    for url in urls:
        logger.info(f"Processing {url}...")
        text = scrape_page(url)
        if text:  # Only generate a description if scraping was successful
            description = generate_description(text)
            results.append({"url": url, "description": description})
        else:
            logger.warning(f"Skipping description generation for {url} due to scraping error.")
            results.append({"url": url, "description": ""})
        time.sleep(2)  # Add a delay between requests to avoid overwhelming the server
    return results

def save_to_json(data, output_file):
    """Save the results to a JSON file."""
    try:
        with open(output_file, 'w') as file:
            json.dump(data, file, indent=4)
        logger.info(f"Descriptions saved to {output_file}")
    except Exception as e:
        logger.error(f"Error saving to {output_file}: {e}")

if __name__ == "__main__":
    # Input and output file paths
    input_file = "urls_docs.txt"
    output_file = "docs_links_with_descriptions.json"

    # Read URLs from the input file
    urls = read_urls_from_file(input_file)
    if not urls:
        logger.error("No URLs found in the input file. Exiting.")
        exit(1)

    # Process URLs and generate descriptions
    results = process_urls(urls)

    # Save the results to a JSON file
    save_to_json(results, output_file)