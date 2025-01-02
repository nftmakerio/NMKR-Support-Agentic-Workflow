from crewai.tools import tool
import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import time
import json
from openai import OpenAI  # Assuming you're using OpenAI's API for summarization
from dotenv import load_dotenv
import os  # Import os to access environment variables

load_dotenv()

# Initialize the OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def fetch_page_content(url):
    """Helper function to fetch the content of a single page."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an error for bad status codes
        return response.text
    except requests.exceptions.RequestException as e:
        return f"Error fetching {url}: {e}"

def extract_internal_links(base_url, html_content):
    """Helper function to extract all internal links from a page."""
    soup = BeautifulSoup(html_content, "html.parser")
    links = set()
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        full_url = urljoin(base_url, href)
        if full_url.startswith(base_url):  # Ensure it's an internal link
            # Exclude specific paths or file types
            excluded_paths = [
                "/login", "/signup", "/logout", "/register", "/password-reset",
                "/admin", "/dashboard", "/wp-admin", "/manager",
                "/privacy", "/terms", "/cookie-policy", "/legal",
                "/api", "/graphql", "/rest",
                "/search", "/cart", "/checkout", "/contact"
            ]
            excluded_extensions = [".pdf", ".jpg", ".png", ".css", ".js", ".zip", ".mp4"]
            if (not any(excluded in full_url for excluded in excluded_paths) and
                not any(full_url.endswith(ext) for ext in excluded_extensions)):
                links.add(full_url)
    return list(links)

def extract_text_from_html(html_content):
    """Helper function to extract and clean text from HTML."""
    soup = BeautifulSoup(html_content, "html.parser")
    # Remove script and style elements
    for script_or_style in soup(["script", "style"]):
        script_or_style.decompose()
    # Get text and clean it
    text = soup.get_text(separator=" ", strip=True)
    return text

def summarize_text(text, max_tokens=500):
    """Summarize the text using an LLM."""
    try:
        response = client.chat.completions.create(
            model="gpt-4",  # or "gpt-3.5-turbo"
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes text while preserving important information."},
                {"role": "user", "content": f"Summarize the following text in a concise manner, ensuring no important information is lost:\n\n{text}"}
            ],
            max_tokens=max_tokens,
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error summarizing text: {e}"

def save_results_to_file(results, filename="crawled_data.json"):
    """Save the crawled results to a JSON file."""
    with open(filename, "w", encoding="utf-8") as file:
        json.dump(results, file, indent=4)
    print(f"Results saved to {filename}")

@tool
def fetch_website_and_subpages(base_urls: list[str], max_pages: int = 10, max_depth: int = 3, delay: float = 1.0) -> dict:
    """
    Fetches the text content of multiple websites and their subpages up to a specified limit, and summarizes the content.

    Args:
        base_urls (list[str]): A list of URLs of the websites to fetch.
        max_pages (int): The maximum number of pages to fetch per website (default: 10).
        max_depth (int): The maximum depth of subpages to crawl (default: 3).
        delay (float): Delay between requests in seconds (default: 1.0).

    Returns:
        dict: A dictionary where keys are URLs and values are the corresponding summarized text content.
    """
    fetched_pages = {}
    for base_url in base_urls:
        pages_to_fetch = [(base_url, 0)]  # (url, depth)
        fetched_count = 0

        while pages_to_fetch and fetched_count < max_pages:
            current_url, current_depth = pages_to_fetch.pop(0)
            if current_url in fetched_pages or current_depth > max_depth:
                continue  # Skip already fetched pages or pages beyond max depth

            print(f"Crawling: {current_url} (Depth: {current_depth})")  # Print the URL being crawled

            # Fetch the content of the current page
            html_content = fetch_page_content(current_url)
            if html_content.startswith("Error fetching"):
                fetched_pages[current_url] = html_content  # Store the error message
            else:
                # Extract and clean the text content
                text_content = extract_text_from_html(html_content)
                # Summarize the text content
                summarized_content = summarize_text(text_content)
                fetched_pages[current_url] = summarized_content
            fetched_count += 1

            # Extract internal links and add them to the queue
            if fetched_count < max_pages and current_depth < max_depth:
                internal_links = extract_internal_links(base_url, html_content)
                pages_to_fetch.extend((link, current_depth + 1) for link in internal_links if link not in fetched_pages)

            time.sleep(delay)  # Add a delay between requests

    save_results_to_file(fetched_pages)  # Save results to a file
    return fetched_pages