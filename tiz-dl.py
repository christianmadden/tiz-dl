#!/usr/bin/env python3
"""
tiz-dl.py - Script to download videos from tiz-cycling.tv and other sites

This script can extract videos from various websites including tiz-cycling.tv
and supports both direct media downloads and YouTube videos.
"""

import requests
from bs4 import BeautifulSoup
import urllib.parse as urlparse
from urllib.parse import parse_qs, urlsplit, unquote
import argparse
import os
import json
import subprocess
import re
import sys
from requests.exceptions import RequestException
from tqdm import tqdm
import yt_dlp

# Global configuration
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

def download_video(url, destination):
    """
    Download a video file directly without using yt-dlp.
    
    Args:
        url (str): Direct URL to the video file
        destination (str): Directory to save the video
    """
    try:
        print(f"Starting direct download of: {url}")
        # Send a HEAD request to get the size of the video
        headers = {'User-Agent': USER_AGENT}
        response = requests.head(url, headers=headers)
        file_size = int(response.headers.get('Content-Length', 0))
        
        # Get the file name from the URL
        file_name = os.path.basename(urlsplit(url).path)
        
        # Fix file name if it contains URL encoded characters
        file_name = unquote(file_name)
        
        # Replace spaces with underscores for safer filenames
        file_name = file_name.replace(' ', '_')
        
        print(f"Downloading file: {file_name} ({file_size} bytes)")
        
        # Full path to save the file
        file_path = os.path.join(destination, file_name)
        
        # If file already exists, ask for confirmation
        if os.path.exists(file_path):
            response = input(f"File '{file_name}' already exists. Overwrite? (y/n): ")
            if response.lower() != 'y':
                print("Download cancelled.")
                return
        
        # Streaming, so we can iterate over the response.
        response = requests.get(url, stream=True, headers=headers)
        response.raise_for_status()  # Raise exception for HTTP errors
        
        # Progress bar setup
        progress = tqdm(response.iter_content(1024), f"Downloading {file_name}", 
                        total=file_size, unit="B", unit_scale=True, unit_divisor=1024)
        
        # Download the video with progress indicator
        with open(file_path, 'wb') as f:
            for data in progress:
                f.write(data)
                progress.update(len(data))
        print(f"Download completed: {file_path}")
        
    except RequestException as e:
        print(f"Request failed: {e}")

def normalize_youtube_url(url):
    """
    Convert YouTube embed URLs to regular watch URLs.
    
    Args:
        url (str): YouTube URL to normalize
        
    Returns:
        str: Normalized YouTube watch URL
    """
    # Handle YouTube embed URLs
    if "/embed/" in url:
        video_id = url.split('/embed/')[1].split('?')[0]
        normalized = f"https://www.youtube.com/watch?v={video_id}"
        print(f"Converted embed URL to: {normalized}")
        return normalized
    
    # Handle youtu.be short URLs
    if "youtu.be/" in url:
        video_id = url.split('youtu.be/')[1].split('?')[0]
        normalized = f"https://www.youtube.com/watch?v={video_id}"
        print(f"Converted short URL to: {normalized}")
        return normalized
    
    # Handle URLs with 'v' parameter
    parsed_url = urlparse.urlparse(url)
    query_params = parse_qs(parsed_url.query)
    if 'v' in query_params:
        video_id = query_params['v'][0]
        normalized = f"https://www.youtube.com/watch?v={video_id}"
        if normalized != url:
            print(f"Normalized YouTube URL to: {normalized}")
        return normalized
        
    return url

def download_youtube_video(video_url, destination, cookies_file=None, quality='best'):
    """
    Downloads a YouTube video using yt-dlp with authentication via cookies.txt.
    
    Args:
        video_url (str): URL of the YouTube video
        destination (str): Directory to save the video
        cookies_file (str, optional): Path to cookies file. If None, will search in multiple locations.
        quality (str): Video quality to download
    """
    try:
        # Normalize YouTube URL
        video_url = normalize_youtube_url(video_url)
        
        # Get the script's directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Search for cookies file in multiple locations
        cookies_locations = [
            cookies_file,  # User-provided path (if any)
            os.path.join(script_dir, "cookies.txt"),  # Same directory as script
            os.path.join(os.getcwd(), "cookies.txt"),  # Current working directory
            os.path.expanduser("~/.config/yt-dlp/cookies.txt")  # Config directory
        ]
        
        # Filter out None values
        cookies_locations = [loc for loc in cookies_locations if loc]
        
        # Find first existing cookies file
        cookies_path = None
        for loc in cookies_locations:
            if os.path.exists(loc):
                cookies_path = loc
                print(f"Found cookies file: {cookies_path}")
                break
        
        if not cookies_path:
            print("Warning: No cookies.txt file found. YouTube might require authentication.")
        
        print(f"\nDownloading YouTube video from: {video_url}")
        
        # Use subprocess approach
        cmd = ["yt-dlp"]
        if cookies_path:
            cmd.extend(["--cookies", cookies_path])
            
        # Add extra options to help with YouTube's protections
        cmd.extend([
            "--geo-bypass",
            "--no-check-certificates",
            "--extractor-retries", "3"
        ])
        
        # Set format based on quality parameter
        if quality == 'best':
            cmd.extend(["-f", "bestvideo*+bestaudio/best"])
        elif quality == 'audio':
            cmd.extend(["-f", "bestaudio", "-x", "--audio-format", "mp3"])
        else:
            cmd.extend(["-f", quality])
            
        cmd.extend([
            "-o", os.path.join(destination, "%(title)s.%(ext)s"),
            "--no-playlist",
            video_url
        ])
        
        print(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"Download completed successfully!")
            return True
        else:
            print(f"YouTube download failed with error:")
            print(result.stderr)
            
            # If cookies failed, try with --cookies-from-browser as fallback
            if cookies_path and "Sign in to confirm you're not a bot" in result.stderr:
                print("\nTrying alternative approach with browser cookies...")
                # Try to find an installed browser
                browsers = ["chrome", "firefox", "edge", "safari", "brave", "opera"]
                for browser in browsers:
                    try:
                        alt_cmd = ["yt-dlp", "--cookies-from-browser", browser, "-f", "bestvideo*+bestaudio/best",
                                "-o", os.path.join(destination, "%(title)s.%(ext)s"), video_url]
                        print(f"Running: {' '.join(alt_cmd)}")
                        alt_result = subprocess.run(alt_cmd, check=False)
                        if alt_result.returncode == 0:
                            print(f"Download successful using {browser} cookies!")
                            return True
                    except Exception:
                        continue
            
            return False

    except Exception as e:
        print(f"Failed to download YouTube video: {e}")
        return False

def extract_tiz_url(url, response_text):
    """
    Extracts the direct video URL from a tiz-cycling.tv page.
    
    Args:
        url (str): The tiz-cycling.tv URL
        response_text (str): HTML content of the page
        
    Returns:
        str or None: Direct video URL if found, None otherwise
    """
    # First try using regex to find the video URL directly in the page source
    mp4_patterns = [
        r'(https?://video\.tiz-cycling\.io/[^"\']+\.mp4)',
        r'(https?://[^"\']+/Tiz-Cycling/[^"\']+\.mp4)',
        r'v=(https?://[^&"\']+\.mp4)'
    ]
    
    for pattern in mp4_patterns:
        mp4_matches = re.findall(pattern, response_text)
        if mp4_matches:
            direct_url = unquote(mp4_matches[0])
            print(f"Found direct video URL in page source: {direct_url}")
            return direct_url

    # Parse the HTML content
    soup = BeautifulSoup(response_text, 'html.parser')
    
    # Check for the presence of YouTube iframes
    youtube_iframes = soup.find_all('iframe', src=lambda s: s and ('youtube.com' in s or 'youtu.be' in s))
    if youtube_iframes:
        youtube_url = youtube_iframes[0]['src']
        print(f"Found YouTube iframe: {youtube_url}")
        return youtube_url
    
    # Check for iframe with video.php source
    iframes = soup.find_all('iframe')
    for iframe in iframes:
        if 'src' in iframe.attrs:
            src = iframe['src']
            if 'video.php' in src:
                # Get the full URL
                video_php_url = urlparse.urljoin(url, src)
                print(f"Found video.php iframe: {video_php_url}")
                
                # Extract v parameter directly
                parsed_iframe = urlparse.urlparse(video_php_url)
                query_params = parse_qs(parsed_iframe.query)
                if 'v' in query_params and query_params['v']:
                    direct_url = unquote(query_params['v'][0])
                    print(f"Found direct video URL in iframe query: {direct_url}")
                    return direct_url
                
                # If necessary, follow the iframe src to get the video URL
                try:
                    iframe_response = requests.get(video_php_url, headers={'User-Agent': USER_AGENT})
                    iframe_soup = BeautifulSoup(iframe_response.text, 'html.parser')
                    
                    # Look for video URLs in this page
                    for pattern in mp4_patterns:
                        iframe_mp4_matches = re.findall(pattern, iframe_response.text)
                        if iframe_mp4_matches:
                            direct_url = unquote(iframe_mp4_matches[0])
                            print(f"Found direct video URL in iframe source: {direct_url}")
                            return direct_url
                except Exception as e:
                    print(f"Error following iframe: {e}")
    
    # Try to find a direct link to video.php with v parameter
    links = soup.find_all('a', href=lambda x: x and 'video.php?v=' in x)
    for link in links:
        href = link['href']
        full_url = urlparse.urljoin(url, href)
        parsed_link = urlparse.urlparse(full_url)
        query_params = parse_qs(parsed_link.query)
        if 'v' in query_params and query_params['v']:
            direct_url = unquote(query_params['v'][0])
            print(f"Found direct video URL in link: {direct_url}")
            return direct_url
    
    # If no MP4 URL found, look for other video files
    video_extensions = ['.mp4', '.mkv', '.mov', '.avi', '.wmv', '.flv', '.webm']
    for ext in video_extensions:
        pattern = r'(https?://[^"\']+\{}[^"\'"]*)'.format(ext)
        matches = re.findall(pattern, response_text)
        if matches:
            direct_url = unquote(matches[0])
            print(f"Found {ext} video URL: {direct_url}")
            return direct_url
    
    return None

def is_youtube_url(url):
    """Check if a URL is a YouTube video URL."""
    return "youtube.com" in url or "youtu.be" in url

def extract_video_url(url, follow_redirects=True):
    """
    Extract video URL from a webpage.
    
    Args:
        url (str): URL of the webpage
        follow_redirects (bool): Whether to follow redirects
        
    Returns:
        str or None: Extracted video URL or None if not found
    """
    try:
        # Handle direct YouTube URLs
        if is_youtube_url(url):
            print(f"Direct YouTube URL detected: {url}")
            return url
            
        # Handle direct video URLs
        video_extensions = ['.mp4', '.mkv', '.mov', '.avi', '.wmv', '.flv', '.webm']
        if any(ext in url.lower() for ext in video_extensions):
            print(f"Direct video URL detected: {url}")
            return url
        
        # Send a GET request to the URL
        headers = {'User-Agent': USER_AGENT}
        print(f"Fetching page: {url}")
        response = requests.get(url, headers=headers)
        
        # Check for redirects if enabled
        if follow_redirects and response.history:
            final_url = response.url
            if final_url != url:
                print(f"Followed redirect to: {final_url}")
                if is_youtube_url(final_url):
                    return final_url
        
        # Special case for tiz-cycling.tv
        if "tiz-cycling.tv" in url:
            # Try to extract the URL using our specialized tiz-cycling extractor
            tiz_url = extract_tiz_url(url, response.text)
            if tiz_url:
                return tiz_url
                
            # If we're on video.php page directly, check the v parameter
            if "video.php" in url:
                parsed_url = urlparse.urlparse(url)
                query_params = parse_qs(parsed_url.query)
                if 'v' in query_params and query_params['v']:
                    direct_url = unquote(query_params['v'][0])
                    print(f"Found direct video URL in query parameter: {direct_url}")
                    return direct_url
        
        # Generic extraction for other websites
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Check for video-wrapper iframe
        video_wrapper = soup.find(class_='video-wrapper')
        iframe = video_wrapper.find('iframe') if video_wrapper else None
        
        if iframe and 'src' in iframe.attrs:
            src = iframe['src']
            parsed_src = urlparse.urlparse(src)
            query_params = parse_qs(parsed_src.query)
            
            # Check for 'v' parameter (YouTube or tiz)
            if 'v' in query_params and query_params['v']:
                v_value = unquote(query_params['v'][0])
                
                # If the v parameter looks like a URL, return it directly
                if v_value.startswith('http'):
                    print(f"Found direct video URL in iframe: {v_value}")
                    return v_value
                
                # Otherwise, assume it's a YouTube video ID
                youtube_url = f"https://www.youtube.com/watch?v={v_value}"
                print(f"Found YouTube video: {youtube_url}")
                return youtube_url
                
            return src
        
        # Check for YouTube embedded video
        youtube_video = soup.find('iframe', src=lambda x: x and "youtube.com" in x)
        if youtube_video and 'src' in youtube_video.attrs:
            src = youtube_video['src']
            return src
        
        # Check for Flowplayer embedded video
        flowplayer_div = soup.find('div', class_='flowplayer')
        if flowplayer_div and 'data-item' in flowplayer_div.attrs:
            try:
                data_item = flowplayer_div['data-item']
                data = json.loads(data_item)
                
                if 'sources' in data and data['sources']:
                    video_url = data['sources'][0]['src']
                    print(f"Flowplayer video found: {video_url}")
                    return video_url
            except json.JSONDecodeError:
                print("Error parsing Flowplayer data")
        
        # Check direct <video> tags
        video_tag = soup.find('video')
        if video_tag:
            # Check for source tags within the video tag
            source_tag = video_tag.find('source')
            if source_tag and 'src' in source_tag.attrs:
                video_url = source_tag['src']
                print(f"Direct video source found: {video_url}")
                return video_url
            
            # Check for src attribute directly on video tag
            if 'src' in video_tag.attrs:
                video_url = video_tag['src']
                print(f"Direct video tag source found: {video_url}")
                return video_url
                
        # Check for direct YouTube links in the page
        youtube_links = soup.find_all('a', href=lambda x: x and ("youtube.com/watch" in x or "youtu.be/" in x))
        if youtube_links:
            youtube_url = youtube_links[0]['href']
            print(f"Found YouTube link: {youtube_url}")
            return youtube_url
            
        # Generic regex search for video URLs
        video_patterns = [
            r'(https?://[^"\']+\.mp4[^"\']*)',
            r'(https?://[^"\']+\.mov[^"\']*)',
            r'(https?://[^"\']+\.webm[^"\']*)'
        ]
        
        for pattern in video_patterns:
            matches = re.findall(pattern, response.text)
            if matches:
                video_url = unquote(matches[0])
                print(f"Found video URL via pattern matching: {video_url}")
                return video_url
            
        return None
        
    except Exception as e:
        print(f"Error extracting video URL: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Extract and download video URL from a webpage.")
    parser.add_argument('--source', '-s', type=str, help="The URL of the webpage to parse.")
    parser.add_argument('--destination', '-d', type=str, default=os.getcwd(), 
                       help="The destination directory to download the video. Default is the current directory.")
    parser.add_argument('--cookies', '-c', type=str, help="Path to cookies.txt file for YouTube videos.")
    parser.add_argument('--direct-youtube', '-y', action='store_true', 
                       help="Treat the source URL as a direct YouTube URL (skip extraction).")
    parser.add_argument('--quality', '-q', choices=['best', 'audio', '720p', '1080p'], default='best',
                       help="Video quality to download (default: best)")
    parser.add_argument('--verbose', '-v', action='store_true', help="Show more detailed output.")
    parser.add_argument('--no-redirects', '-nr', action='store_true', help="Don't follow redirects when extracting URLs.")
    
    args = parser.parse_args()
    
    # Prompt for URL if not provided as argument
    if not args.source:
        args.source = input("Please enter the URL of the webpage or YouTube video: ")

    # Ensure destination directory exists
    if not os.path.isdir(args.destination):
        print(f"Creating directory: {args.destination}")
        os.makedirs(args.destination)
    
    # Extract the video URL unless direct-youtube flag is set
    if args.direct_youtube:
        video_url = args.source
        print(f"Using direct YouTube URL: {video_url}")
    else:
        # Extract the video URL
        video_url = extract_video_url(args.source, not args.no_redirects)
    
    if video_url:
        print(f"Final video URL: {video_url}")
        
        # Check for YouTube URLs
        if is_youtube_url(video_url):
            print("Detected as YouTube video, using YouTube download method")
            download_youtube_video(video_url, args.destination, args.cookies, args.quality)
        elif video_url.endswith(('.mp4', '.mkv', '.mov', '.webm', '.avi')):
            print("Detected as direct media file, using direct download method")
            download_video(video_url, args.destination)
        else:
            # If URL doesn't have a recognizable video extension, try yt-dlp first
            print("URL type uncertain, trying YouTube download first")
            if not download_youtube_video(video_url, args.destination, args.cookies, args.quality):
                print("Falling back to direct download")
                download_video(video_url, args.destination)
    else:
        print("No video URL found or the video URL does not contain a direct video link.")

if __name__ == "__main__":
    main()