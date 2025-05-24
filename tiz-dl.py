#!/usr/bin/env python3
"""
Video Downloader - Clean script to download videos from various websites

This script extracts and downloads videos from websites including tiz-cycling.tv,
YouTube, and direct video links with improved error handling and cleaner output.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote, urljoin, urlparse, urlsplit

import requests
from bs4 import BeautifulSoup
from requests.exceptions import RequestException
from tqdm import tqdm

# Configuration
USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
)
VIDEO_EXTENSIONS = ['.mp4', '.mkv', '.mov', '.avi', '.wmv', '.flv', '.webm']


class VideoDownloader:
    """Main class for handling video downloads"""
    
    def __init__(self, destination, cookies_file=None, verbose=False):
        self.destination = Path(destination)
        self.cookies_file = cookies_file
        self.verbose = verbose
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})
        
        # Ensure destination exists
        self.destination.mkdir(parents=True, exist_ok=True)
    
    def log(self, message, level='info'):
        """Clean logging with optional verbose mode"""
        if level == 'error':
            print(f"❌ {message}", file=sys.stderr)
        elif level == 'success':
            print(f"✅ {message}")
        elif level == 'info':
            print(f"ℹ️  {message}")
        elif level == 'verbose' and self.verbose:
            print(f"🔍 {message}")
    
    def is_youtube_url(self, url):
        """Check if URL is a YouTube video"""
        return any(domain in url for domain in ['youtube.com', 'youtu.be'])
    
    def is_direct_video_url(self, url):
        """Check if URL points directly to a video file"""
        return any(ext in url.lower() for ext in VIDEO_EXTENSIONS)
    
    def normalize_youtube_url(self, url):
        """Convert various YouTube URL formats to standard watch URL"""
        # Handle embed URLs
        if '/embed/' in url:
            video_id = url.split('/embed/')[1].split('?')[0]
            return f"https://www.youtube.com/watch?v={video_id}"
        
        # Handle short URLs
        if 'youtu.be/' in url:
            video_id = url.split('youtu.be/')[1].split('?')[0]
            return f"https://www.youtube.com/watch?v={video_id}"
        
        # Handle URLs with 'v' parameter
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        if 'v' in query_params:
            video_id = query_params['v'][0]
            return f"https://www.youtube.com/watch?v={video_id}"
        
        return url
    
    def find_cookies_file(self):
        """Find cookies.txt file in common locations"""
        if self.cookies_file and Path(self.cookies_file).exists():
            return self.cookies_file
        
        script_dir = Path(__file__).parent
        locations = [
            script_dir / "cookies.txt",
            Path.cwd() / "cookies.txt",
            Path.home() / ".config" / "yt-dlp" / "cookies.txt"
        ]
        
        for location in locations:
            if location.exists():
                self.log(f"Found cookies file: {location}", 'verbose')
                return str(location)
        
        return None
    
    def download_direct_video(self, url):
        """Download video file directly"""
        try:
            self.log(f"Starting direct download: {url}")
            
            # Get file info
            response = self.session.head(url)
            response.raise_for_status()
            
            file_size = int(response.headers.get('Content-Length', 0))
            file_name = Path(urlsplit(url).path).name
            file_name = unquote(file_name).replace(' ', '_')
            
            if not file_name or file_name == '/':
                file_name = 'video.mp4'
            
            file_path = self.destination / file_name
            
            # Check if file exists
            if file_path.exists():
                response = input(f"File '{file_name}' exists. Overwrite? (y/N): ")
                if response.lower() != 'y':
                    self.log("Download cancelled")
                    return False
            
            # Download with progress bar
            response = self.session.get(url, stream=True)
            response.raise_for_status()
            
            with tqdm(
                total=file_size,
                unit='B',
                unit_scale=True,
                desc=f"Downloading {file_name}"
            ) as pbar:
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))
            
            self.log(f"Downloaded: {file_path}", 'success')
            return True
            
        except RequestException as e:
            self.log(f"Download failed: {e}", 'error')
            return False
    
    def download_youtube_video(self, url, quality='best'):
        """Download YouTube video using yt-dlp"""
        try:
            url = self.normalize_youtube_url(url)
            self.log(f"Downloading YouTube video: {url}")
            
            # Build yt-dlp command
            cmd = ['yt-dlp']
            
            # Add cookies if available
            cookies_path = self.find_cookies_file()
            if cookies_path:
                cmd.extend(['--cookies', cookies_path])
            else:
                self.log("No cookies file found - some videos may be unavailable", 'verbose')
            
            # Format selection
            format_map = {
                'best': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'audio': 'bestaudio',
                '720p': 'best[height<=720]',
                '1080p': 'best[height<=1080]'
            }
            
            cmd.extend(['-f', format_map.get(quality, quality)])
            
            # Audio extraction for audio-only
            if quality == 'audio':
                cmd.extend(['-x', '--audio-format', 'mp3'])
            
            # Output template and other options
            output_template = str(self.destination / '%(title)s.%(ext)s')
            cmd.extend([
                '-o', output_template,
                '--no-playlist',
                '--geo-bypass',
                '--extractor-retries', '3',
                url
            ])
            
            self.log(f"Running: {' '.join(cmd[:-1])} [URL]", 'verbose')
            
            # Execute command
            result = subprocess.run(
                cmd,
                capture_output=not self.verbose,
                text=True
            )
            
            if result.returncode == 0:
                self.log("YouTube download completed", 'success')
                return True
            else:
                self.log("YouTube download failed", 'error')
                if not self.verbose and result.stderr:
                    self.log(f"Error: {result.stderr}", 'error')
                
                # Try browser cookies as fallback
                return self._try_browser_cookies(url, output_template)
                
        except Exception as e:
            self.log(f"YouTube download error: {e}", 'error')
            return False
    
    def _try_browser_cookies(self, url, output_template):
        """Fallback: try downloading with browser cookies"""
        self.log("Trying browser cookies as fallback...", 'verbose')
        
        browsers = ['chrome', 'firefox', 'edge', 'safari']
        for browser in browsers:
            try:
                cmd = [
                    'yt-dlp',
                    '--cookies-from-browser', browser,
                    '-f', 'best[ext=mp4]/best',
                    '-o', output_template,
                    url
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    self.log(f"Success using {browser} cookies", 'success')
                    return True
                    
            except Exception:
                continue
        
        return False
    
    def extract_tiz_cycling_url(self, url, html_content):
        """Extract video URL from tiz-cycling.tv pages"""
        # Try regex patterns first
        patterns = [
            r'(https?://video\.tiz-cycling\.io/[^"\']+\.mp4)',
            r'(https?://[^"\']+/Tiz-Cycling/[^"\']+\.mp4)',
            r'v=(https?://[^&"\']+\.mp4)'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html_content)
            if matches:
                return unquote(matches[0])
        
        # Parse HTML structure
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Check for YouTube iframes
        youtube_iframes = soup.find_all(
            'iframe',
            src=lambda s: s and ('youtube.com' in s or 'youtu.be' in s)
        )
        if youtube_iframes:
            return youtube_iframes[0]['src']
        
        # Check for video.php iframes
        for iframe in soup.find_all('iframe'):
            src = iframe.get('src', '')
            if 'video.php' in src:
                full_url = urljoin(url, src)
                parsed = urlparse(full_url)
                query_params = parse_qs(parsed.query)
                
                if 'v' in query_params and query_params['v']:
                    return unquote(query_params['v'][0])
        
        return None
    
    def extract_video_url(self, url):
        """Extract video URL from webpage"""
        try:
            # Handle direct cases
            if self.is_youtube_url(url):
                return url
            
            if self.is_direct_video_url(url):
                return url
            
            # Fetch webpage
            self.log(f"Fetching webpage: {url}", 'verbose')
            response = self.session.get(url)
            response.raise_for_status()
            
            # Handle redirects to YouTube
            if self.is_youtube_url(response.url):
                return response.url
            
            # Site-specific extraction
            if 'tiz-cycling.tv' in url:
                extracted = self.extract_tiz_cycling_url(url, response.text)
                if extracted:
                    return extracted
            
            # Generic extraction
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Check video wrapper iframes
            video_wrapper = soup.find(class_='video-wrapper')
            if video_wrapper:
                iframe = video_wrapper.find('iframe')
                if iframe and iframe.get('src'):
                    return iframe['src']
            
            # Check for YouTube iframes
            youtube_iframe = soup.find(
                'iframe',
                src=lambda x: x and 'youtube.com' in x
            )
            if youtube_iframe:
                return youtube_iframe['src']
            
            # Check direct video tags
            video_tag = soup.find('video')
            if video_tag:
                source = video_tag.find('source')
                if source and source.get('src'):
                    return source['src']
                if video_tag.get('src'):
                    return video_tag['src']
            
            # Regex search for video URLs
            for ext in VIDEO_EXTENSIONS:
                pattern = rf'(https?://[^"\']+\{ext}[^"\']*)'
                matches = re.findall(pattern, response.text)
                if matches:
                    return unquote(matches[0])
            
            return None
            
        except Exception as e:
            self.log(f"URL extraction failed: {e}", 'error')
            return None
    
    def download(self, url, quality='best'):
        """Main download method"""
        self.log(f"Processing URL: {url}")
        
        # Extract video URL if needed
        video_url = self.extract_video_url(url)
        if not video_url:
            self.log("No video URL found", 'error')
            return False
        
        self.log(f"Video URL: {video_url}", 'verbose')
        
        # Choose download method
        if self.is_youtube_url(video_url):
            self.log("Detected: YouTube video")
            return self.download_youtube_video(video_url, quality)
        elif self.is_direct_video_url(video_url):
            self.log("Detected: Direct video file")
            return self.download_direct_video(video_url)
        else:
            # Try YouTube first, then direct download
            self.log("Unknown video type, trying YouTube method first")
            if not self.download_youtube_video(video_url, quality):
                self.log("Falling back to direct download")
                return self.download_direct_video(video_url)
            return True


def main():
    parser = argparse.ArgumentParser(
        description="Download videos from various websites",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -s "https://youtube.com/watch?v=VIDEO_ID"
  %(prog)s -s "https://tiz-cycling.tv/video/..." -d ~/Downloads
  %(prog)s -s "https://example.com/video.mp4" -q 720p
        """
    )
    
    parser.add_argument(
        '-s', '--source',
        help="URL of the webpage or video to download"
    )
    parser.add_argument(
        '-d', '--destination',
        default=os.getcwd(),
        help="Download directory (default: current directory)"
    )
    parser.add_argument(
        '-c', '--cookies',
        help="Path to cookies.txt file for authentication"
    )
    parser.add_argument(
        '-q', '--quality',
        choices=['best', 'audio', '720p', '1080p'],
        default='best',
        help="Video quality (default: best)"
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help="Show detailed output"
    )
    
    args = parser.parse_args()
    
    # Get URL if not provided
    if not args.source:
        args.source = input("Enter the URL to download: ").strip()
        if not args.source:
            print("❌ No URL provided")
            sys.exit(1)
    
    # Create downloader and process
    downloader = VideoDownloader(
        destination=args.destination,
        cookies_file=args.cookies,
        verbose=args.verbose
    )
    
    success = downloader.download(args.source, args.quality)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()