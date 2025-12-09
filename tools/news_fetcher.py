import requests
import json
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import sqlite3
import uuid

# --- Stage 1: Scraping and Parsing Functions (Largely unchanged) ---

def extract_nhk_news_info(html_content):
    """
    Analyzes the structure of an NHK news article HTML and extracts key information.
    
    Args:
        html_content: A string containing the HTML content of the news page.

    Returns:
        A dictionary containing the extracted news title, content, category, and timestamp.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    extracted_data = {
        "title": None,
        "category": None,
        "timestamp": None,
        "content": None
    }

    # Strategy 1: Use JSON-LD (Schema.org) for structured metadata
    news_article_data = None
    json_ld_scripts = soup.find_all('script', type='application/ld+json')
    
    for script in json_ld_scripts:
        if script.string:
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    for item in data:
                        if item.get('@type') == 'NewsArticle':
                            news_article_data = item; break
                elif isinstance(data, dict) and data.get('@type') == 'NewsArticle':
                    news_article_data = data
                if news_article_data: break
            except (json.JSONDecodeError, AttributeError): continue

    if news_article_data:
        extracted_data["title"] = news_article_data.get('headline')
        extracted_data["timestamp"] = news_article_data.get('datePublished')
        if news_article_data.get('genre'):
            extracted_data["category"] = ", ".join(news_article_data.get('genre'))

    # Strategy 2: Fallback to HTML tag parsing if needed
    if not extracted_data["title"]:
        title_tag = soup.find('h1', class_='content--title')
        if title_tag: extracted_data["title"] = title_tag.get_text(strip=True)

    if not extracted_data["timestamp"]:
        time_tag = soup.find('time')
        if time_tag and 'datetime' in time_tag.attrs:
            extracted_data["timestamp"] = time_tag['datetime']

    if not extracted_data["category"]:
        category_tag = soup.select_one('.content--date .i-word')
        if category_tag: extracted_data["category"] = category_tag.get_text(strip=True)

    # --- Content Extraction ---
    content_parts = []
    summary_p = soup.find('p', class_='content--summary')
    if summary_p: content_parts.append(summary_p.get_text(strip=True))

    article_body = soup.select_one('.content--detail-more')
    if article_body:
        for element in article_body.find_all(['section', 'h2'], recursive=False):
            if element.name == 'h2' and 'body-title' in element.get('class', []):
                content_parts.append(f"\n--- {element.get_text(strip=True)} ---\n")
            elif element.name == 'section' and 'content--body' in element.get('class', []):
                text_div = element.find('div', class_='body-text')
                if text_div: content_parts.append(text_div.get_text(separator='\n', strip=True))

    if content_parts: extracted_data["content"] = "\n\n".join(content_parts)
        
    return extracted_data

def get_urls_from_rss(rss_url):
    """
    Fetches an RSS feed and parses it to extract news article URLs.
    """
    try:
        response = requests.get(rss_url, timeout=10)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        urls = [item.find('link').text for item in root.findall('./channel/item')]
        return urls
    except requests.exceptions.RequestException as e:
        print(f"Error fetching RSS feed: {e}")
        return []
    except ET.ParseError as e:
        print(f"Error parsing XML from RSS feed: {e}")
        return []

# --- Stage 2: New Database Function ---

def save_articles_to_db(articles_data, db_name='news_corpus.db'):
    """
    Saves a list of scraped articles into a SQLite database.
    Creates the table if it doesn't exist and ignores duplicates.

    Args:
        articles_data (list): A list of dictionaries, where each dictionary is a scraped article.
        db_name (str): The name of the SQLite database file.
    """
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # Create table with a schema adapted from the pseudo-code
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            article_id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            url TEXT UNIQUE NOT NULL,
            title TEXT,
            category TEXT,
            publish_timestamp TEXT,
            body_text TEXT,
            status TEXT NOT NULL
        )
    ''')

    new_articles_count = 0
    for article in articles_data:
        # Generate a unique and consistent ID from the URL to prevent duplicates
        article_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, article['url']))
        
        # Use INSERT OR IGNORE to gracefully handle articles that already exist
        cursor.execute('''
            INSERT OR IGNORE INTO articles (
                article_id, source, url, title, category, publish_timestamp, body_text, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            article_id, 
            'NHK News', 
            article.get('url'), 
            article.get('title'), 
            article.get('category'),
            article.get('timestamp'), 
            article.get('content'), 
            'unprocessed'
        ))
        
        # cursor.rowcount is 1 if a new row was inserted, 0 if it was ignored
        new_articles_count += cursor.rowcount

    conn.commit()
    conn.close()
    
    print(f"Database operation complete. Added {new_articles_count} new articles.")

# --- Stage 3: Main Execution Logic ---

def scrape_and_store_latest_nhk_news():
    """
    Orchestrates the entire process of fetching URLs from RSS, scraping each page,
    and storing the results in the database.
    """
    rss_feed_url = "https://www.nhk.or.jp/rss/news/cat0.xml"
    print(f"Fetching latest news URLs from: {rss_feed_url}")
    
    news_urls = get_urls_from_rss(rss_feed_url)
    
    if not news_urls:
        print("No URLs found in the RSS feed. Exiting.")
        return []

    print(f"Found {len(news_urls)} articles in the feed.")
    
    all_news_data = []
    for i, url in enumerate(news_urls, 1):
        print(f"Scraping article {i}/{len(news_urls)}: {url}")
        try:
            page_response = requests.get(url, timeout=10)
            page_response.raise_for_status()
            
            page_response.encoding = 'utf-8'

            article_data = extract_nhk_news_info(page_response.text)
            article_data['url'] = url
            
            all_news_data.append(article_data)
        except requests.exceptions.RequestException as e:
            print(f"  -> Failed to scrape {url}: {e}")
        except Exception as e:
            print(f"  -> An unexpected error occurred while processing {url}: {e}")
    
    # After scraping, save the collected data to the database
    if all_news_data:
        print(f"\n--- Saving {len(all_news_data)} scraped articles to the database... ---")
        save_articles_to_db(all_news_data)

if __name__ == "__main__":
    scrape_and_store_latest_nhk_news()
    print("\nProcess finished.")