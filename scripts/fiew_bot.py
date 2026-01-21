#!/usr/bin/env python3
"""
Fiew Facebook Page Bot
Automatically posts markdown content or daily messages to Facebook page.
Designed for GitHub Actions.
"""

import os
import yaml
import logging
import random
from datetime import datetime, date
from pathlib import Path
import facebook
import markdown
from typing import Optional, Dict, Any
import json
import sys

class FiewBot:
    def __init__(self, config_path: str = "config/config.yaml"):
        """Initialize the Fiew bot with configuration."""
        self.config = self.load_config(config_path)
        self.setup_logging()
        self.graph = None
        self.test_mode = os.getenv('TEST_MODE', 'false').lower() == 'true'
        self.authenticate()
        
    def load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
        except FileNotFoundError:
            config = {
                'paths': {
                    'posts_dir': 'posts/',
                    'logs_dir': 'logs/'
                },
                'content': {
                    'default_message': '🌞 Good morning from Fiew! Stay curious, stay inspired. #FiewDaily',
                    'fallback_messages': [
                        'Another day, another opportunity to learn something new! 📚',
                        'Keep exploring, keep growing. What will you discover today?',
                        'Thought for the day: The only limit is your imagination. ✨'
                    ]
                }
            }
        
        # Get values from environment variables (GitHub Secrets)
        env_config = {
            'facebook': {
                'page_id': os.getenv('FB_PAGE_ID'),
                'access_token': os.getenv('FB_ACCESS_TOKEN'),
                'api_version': os.getenv('FB_API_VERSION', 'v18.0')
            }
        }
        
        # Merge configs
        if 'facebook' not in config:
            config['facebook'] = {}
        
        for key, value in env_config['facebook'].items():
            if value:
                config['facebook'][key] = value
        
        return config
    
    def setup_logging(self):
        """Setup logging configuration."""
        log_dir = self.config['paths'].get('logs_dir', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = f"{log_dir}/fiew_bot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        self.logger.info(f"Logging to: {log_file}")
        self.logger.info(f"Test mode: {self.test_mode}")
    
    def authenticate(self):
        """Authenticate with Facebook Graph API."""
        try:
            access_token = self.config['facebook'].get('access_token')
            if not access_token:
                raise ValueError("No Facebook access token configured")
            
            api_version = self.config['facebook'].get('api_version', 'v18.0')
            self.graph = facebook.GraphAPI(access_token=access_token, version=api_version)
            
            # Test authentication
            if not self.test_mode:
                user = self.graph.get_object('me')
                self.logger.info(f"Successfully authenticated as: {user.get('name')}")
            else:
                self.logger.info("Test mode: Skipping actual authentication")
                
        except Exception as e:
            self.logger.error(f"Authentication failed: {e}")
            if not self.test_mode:
                raise
    
    def find_new_post(self) -> Optional[str]:
        """Find a new markdown post to publish."""
        posts_dir = Path(self.config['paths'].get('posts_dir', 'posts'))
        if not posts_dir.exists():
            os.makedirs(posts_dir, exist_ok=True)
            self.logger.info(f"Created posts directory: {posts_dir}")
            return None
        
        # Look for markdown files that haven't been posted yet
        markdown_files = list(posts_dir.glob("*.md"))
        
        if not markdown_files:
            self.logger.info("No markdown files found in posts directory")
            return None
        
        # Sort by filename (alphabetical) or modification time
        markdown_files.sort(key=lambda x: x.name.lower())
        
        # Read the first markdown file
        post_file = markdown_files[0]
        with open(post_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Move to archive after reading
        archive_dir = posts_dir / "archive"
        archive_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archived_path = archive_dir / f"{post_file.stem}_{timestamp}{post_file.suffix}"
        
        if not self.test_mode:
            post_file.rename(archived_path)
            self.logger.info(f"Archived post: {post_file.name} -> {archived_path.name}")
        else:
            self.logger.info(f"Test mode: Would archive {post_file.name}")
        
        return content
    
    def generate_daily_message(self) -> str:
        """Generate a daily message if no post is available."""
        today = date.today()
        
        # Special messages for specific dates
        special_dates = {
            (1, 1): "🎉 Happy New Year! May this year be filled with discovery and growth! #NewYear",
            (2, 14): "💝 Happy Valentine's Day! Remember to love what you do and do what you love. #ValentinesDay",
            (3, 8): "🌸 Happy International Women's Day! Celebrating women in tech and beyond. #WomensDay",
            (4, 22): "🌍 Happy Earth Day! Let's protect our beautiful planet. #EarthDay",
            (12, 25): "🎄 Merry Christmas! Wishing you peace, joy, and inspiration! #Christmas",
            (10, 31): "🎃 Happy Halloween! May your day be spooktacular! #Halloween",
        }
        
        current_month_day = (today.month, today.day)
        if current_month_day in special_dates:
            return special_dates[current_month_day]
        
        # Day of week themes
        day_themes = [
            "Mindfulness Monday ✨",
            "Tech Tuesday 💻",
            "Wisdom Wednesday 📚",
            "Throwback Thursday 🔙",
            "Future Friday 🚀",
            "Science Saturday 🔬",
            "Serenity Sunday ☮️"
        ]
        
        theme = day_themes[today.weekday()]
        
        # Fallback messages
        fallback_messages = self.config['content'].get('fallback_messages', [])
        if fallback_messages:
            message = random.choice(fallback_messages)
            return f"{theme}: {message}"
        else:
            default_msg = self.config['content'].get('default_message', 
                '🌞 Good morning from Fiew! Stay curious, stay inspired.')
            return f"{theme}: {default_msg}"
    
    def convert_markdown_to_facebook_post(self, markdown_content: str) -> str:
        """Convert markdown to Facebook-friendly text."""
        try:
            # Simple markdown parsing
            lines = markdown_content.strip().split('\n')
            result = []
            
            for line in lines:
                # Remove headers
                if line.startswith('# '):
                    result.append(line[2:].strip() + '\n')
                elif line.startswith('## '):
                    result.append(line[3:].strip() + '\n')
                elif line.startswith('### '):
                    result.append(line[4:].strip() + ': ')
                elif line.startswith('>'):
                    result.append('💬 ' + line[1:].strip() + '\n')
                elif line.startswith('* ') or line.startswith('- '):
                    result.append('• ' + line[2:].strip() + '\n')
                elif line.startswith('1. '):
                    result.append(line + '\n')
                elif line.strip() == '---' or line.strip() == '***':
                    result.append('─' * 30 + '\n')
                elif line.strip():
                    result.append(line.strip() + '\n')
                else:
                    result.append('\n')
            
            text = ''.join(result)
            
            # Add hashtags
            text += "\n\n#Fiew #DailyPost #Curiosity"
            
            # Limit length for Facebook
            if len(text) > 5000:
                text = text[:4997] + "..."
            
            return text.strip()
            
        except Exception as e:
            self.logger.error(f"Error converting markdown: {e}")
            return markdown_content[:2000]  # Fallback to truncated original
    
    def post_to_facebook(self, message: str, link: Optional[str] = None) -> bool:
        """Post a message to the Facebook page."""
        if self.test_mode:
            self.logger.info("TEST MODE - Would post to Facebook:")
            self.logger.info(f"Message: {message[:100]}...")
            if link:
                self.logger.info(f"Link: {link}")
            return True
        
        try:
            page_id = self.config['facebook'].get('page_id')
            if not page_id:
                raise ValueError("No Facebook page ID configured")
            
            if link:
                self.graph.put_object(
                    parent_object=page_id,
                    connection_name="feed",
                    message=message,
                    link=link
                )
            else:
                self.graph.put_object(
                    parent_object=page_id,
                    connection_name="feed",
                    message=message
                )
            
            self.logger.info(f"Successfully posted to Facebook page: {page_id}")
            return True
            
        except facebook.GraphAPIError as e:
            self.logger.error(f"Facebook API Error: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error while posting: {e}")
            return False
    
    def run(self):
        """Main posting routine."""
        self.logger.info("Starting Fiew Facebook poster...")
        self.logger.info(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Try to find a new markdown post
        markdown_content = self.find_new_post()
        
        if markdown_content:
            # Convert markdown to Facebook-friendly text
            post_message = self.convert_markdown_to_facebook_post(markdown_content)
            self.logger.info("Using markdown content for post")
            source = "Markdown file"
        else:
            # Generate daily message
            post_message = self.generate_daily_message()
            self.logger.info("Using generated daily message")
            source = "Generated message"
        
        self.logger.info(f"Post message ({len(post_message)} chars) from {source}:")
        self.logger.info("-" * 50)
        self.logger.info(post_message[:500] + ("..." if len(post_message) > 500 else ""))
        self.logger.info("-" * 50)
        
        # Post to Facebook
        success = self.post_to_facebook(post_message)
        
        if success:
            if self.test_mode:
                self.logger.info("✅ Test completed successfully (no actual post made)")
            else:
                self.logger.info("✅ Successfully posted to Facebook")
        else:
            self.logger.error("❌ Failed to post to Facebook")
        
        return success

def main():
    """Main entry point."""
    try:
        bot = FiewBot()
        success = bot.run()
        
        if success:
            return 0
        else:
            return 1
            
    except Exception as e:
        logging.error(f"Fiew Bot failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
