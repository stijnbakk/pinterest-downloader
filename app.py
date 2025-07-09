from flask import Flask, request, jsonify, send_file
import requests
import os
import tempfile
import re
from urllib.parse import urlparse
import uuid
from io import BytesIO
import logging
import shutil
from pinscrape.pinscrape import scraper

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

class PinterestImageScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def extract_pin_id(self, url):
        """Extract pin ID from Pinterest URL"""
        # Handle various Pinterest URL formats
        patterns = [
            r'/pin/(\d+)',
            r'pinterest\.com/pin/(\d+)',
            r'pinterest\.com.*?/pin/(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    def get_pin_data(self, pin_id):
        """Get pin data from Pinterest API endpoint"""
        try:
            api_url = f"https://www.pinterest.com/resource/PinResource/get/"
            params = {
                'source_url': f'/pin/{pin_id}/',
                'data': f'{{"options":{{"pin_id":"{pin_id}"}},"context":{{}}}}'
            }
            
            response = self.session.get(api_url, params=params)
            if response.status_code == 200:
                data = response.json()
                if 'resource_response' in data and 'data' in data['resource_response']:
                    pin_data = data['resource_response']['data']
                    return pin_data
        except Exception as e:
            logging.error(f"Error getting pin data: {e}")
        return None
    
    def get_image_url(self, pinterest_url):
        """Extract the best quality image URL from Pinterest URL"""
        pin_id = self.extract_pin_id(pinterest_url)
        if not pin_id:
            return None
            
        pin_data = self.get_pin_data(pin_id)
        if not pin_data:
            # Fallback to web scraping
            return self.scrape_image_from_page(pinterest_url)
            
        # Try to get the highest quality image
        images = pin_data.get('images', {})
        
        # Priority order for image quality
        quality_keys = ['orig', '736x', '564x', '474x', '236x']
        
        for key in quality_keys:
            if key in images and 'url' in images[key]:
                return images[key]['url']
                
        return None
    
    def scrape_image_from_page(self, url):
        """Fallback method to scrape image from Pinterest page"""
        try:
            response = self.session.get(url)
            if response.status_code == 200:
                content = response.text
                # Look for image URLs in the page content
                img_patterns = [
                    r'"orig":\s*{"url":\s*"([^"]+)"',
                    r'"736x":\s*{"url":\s*"([^"]+)"',
                    r'content="([^"]+\.jpg[^"]*)"',
                    r'content="([^"]+\.png[^"]*)"'
                ]
                
                for pattern in img_patterns:
                    matches = re.findall(pattern, content)
                    if matches:
                        # Clean up the URL (handle escaped characters)
                        img_url = matches[0].replace('\\/', '/')
                        return img_url
        except Exception as e:
            logging.error(f"Error scraping page: {e}")
        return None
    
    def download_image(self, image_url):
        """Download image and return as BytesIO object"""
        try:
            response = self.session.get(image_url, stream=True)
            if response.status_code == 200:
                return BytesIO(response.content)
        except Exception as e:
            logging.error(f"Error downloading image: {e}")
        return None

class PinterestKeywordScraper:
    def __init__(self):
        self.temp_dir = None
    
    def search_and_get_first_image(self, keyword, max_images=1):
        """Search Pinterest by keyword and return the first image"""
        try:
            # Create temporary directory
            self.temp_dir = tempfile.mkdtemp()
            
            # Configure scraper parameters
            proxies = {}
            number_of_workers = 1
            
            # Scrape images
            details = scraper.scrape(
                keyword=keyword,
                output_folder=self.temp_dir,
                proxies=proxies,
                number_of_workers=number_of_workers,
                images_to_download=max_images
            )
            
            if details.get("isDownloaded") and details.get("urls_list"):
                # Find the first downloaded image
                for root, dirs, files in os.walk(self.temp_dir):
                    for file in files:
                        if file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                            image_path = os.path.join(root, file)
                            with open(image_path, 'rb') as f:
                                image_data = BytesIO(f.read())
                            self._cleanup()
                            return image_data, file
                            
            self._cleanup()
            return None, None
            
        except Exception as e:
            logging.error(f"Error in keyword search: {e}")
            self._cleanup()
            return None, None
    
    def _cleanup(self):
        """Clean up temporary directory"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
            except Exception as e:
                logging.error(f"Error cleaning up temp dir: {e}")

@app.route('/')
def home():
    return jsonify({
        "message": "Pinterest Image Scraper API",
        "endpoints": {
            "/scrape": "POST - Send Pinterest URL or keyword to get image",
            "/health": "GET - Health check"
        },
        "usage": [
            {
                "method": "POST",
                "endpoint": "/scrape",
                "body": {"url": "https://pinterest.com/pin/123456789/"},
                "description": "Download image from specific Pinterest URL"
            },
            {
                "method": "POST", 
                "endpoint": "/scrape",
                "body": {"keyword": "landscape photography"},
                "description": "Search and download first image matching keyword"
            }
        ]
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

@app.route('/scrape', methods=['POST'])
def scrape_pinterest():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "Missing request body"}), 400
        
        # Check if it's a URL-based request
        if 'url' in data:
            pinterest_url = data['url']
            
            # Validate Pinterest URL
            if 'pinterest.com' not in pinterest_url:
                return jsonify({"error": "Invalid Pinterest URL"}), 400
            
            scraper_instance = PinterestImageScraper()
            
            # Get image URL
            image_url = scraper_instance.get_image_url(pinterest_url)
            if not image_url:
                return jsonify({"error": "Could not extract image from Pinterest URL"}), 404
            
            # Download image
            image_data = scraper_instance.download_image(image_url)
            if not image_data:
                return jsonify({"error": "Could not download image"}), 500
            
            # Determine file extension
            ext = 'jpg'
            if '.png' in image_url.lower():
                ext = 'png'
            elif '.gif' in image_url.lower():
                ext = 'gif'
            
            # Generate filename
            filename = f"pinterest_url_{uuid.uuid4().hex[:8]}.{ext}"
            
            # Return image file
            image_data.seek(0)
            return send_file(
                image_data,
                as_attachment=True,
                download_name=filename,
                mimetype=f'image/{ext}'
            )
        
        # Check if it's a keyword-based request
        elif 'keyword' in data:
            keyword = data['keyword']
            
            if not keyword or not isinstance(keyword, str):
                return jsonify({"error": "Invalid keyword"}), 400
            
            keyword_scraper = PinterestKeywordScraper()
            
            # Search and get first image
            image_data, original_filename = keyword_scraper.search_and_get_first_image(keyword)
            
            if not image_data:
                return jsonify({"error": f"Could not find images for keyword: {keyword}"}), 404
            
            # Determine file extension from original filename or default to jpg
            ext = 'jpg'
            if original_filename:
                if '.' in original_filename:
                    ext = original_filename.split('.')[-1].lower()
            
            # Generate filename
            safe_keyword = re.sub(r'[^a-zA-Z0-9_-]', '_', keyword)[:20]
            filename = f"pinterest_search_{safe_keyword}_{uuid.uuid4().hex[:8]}.{ext}"
            
            # Return image file
            image_data.seek(0)
            return send_file(
                image_data,
                as_attachment=True,
                download_name=filename,
                mimetype=f'image/{ext}'
            )
        
        else:
            return jsonify({"error": "Missing 'url' or 'keyword' in request body"}), 400
        
    except Exception as e:
        logging.error(f"Error in scrape_pinterest: {e}")
        return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    try:
        app.run(host='0.0.0.0', port=port)
    except Exception as e:
        logging.error(f"Error starting app on port {port}: {e}. Trying port 8081.")
        port = 8081
        app.run(host='0.0.0.0', port=port)
