import requests
from bs4 import BeautifulSoup
import urllib.parse as urlparse
from urllib.parse import parse_qs, urlsplit
import argparse
import os
import json
import subprocess
from requests.exceptions import RequestException
from tqdm import tqdm
import yt_dlp
import sys

def download_video(url, destination):
    try:
        # Send a HEAD request to get the size of the video
        response = requests.head(url)
        file_size = int(response.headers.get('Content-Length', 0))
        
        # Get the file name from the URL
        file_name = os.path.basename(urlsplit(url).path)
        
        # Check if the file extension is one of the video formats
        if file_name.split('.')[-1].lower() in ['mp4', 'mkv', 'mov']:
            # Full path to save the file
            file_path = os.path.join(destination, file_name)
            
            # Streaming, so we can iterate over the response.
            response = requests.get(url, stream=True)
            
            # Progress bar setup
            progress = tqdm(response.iter_content(1024), f"Downloading {file_name}", total=file_size, unit="B", unit_scale=True, unit_divisor=1024)
            
            # Download the video with progress indicator
            with open(file_path, 'wb') as f:
                for data in progress:
                    f.write(data)
                    progress.update(len(data))
            print(f"Download completed: {file_path}")
        else:
            print("The file is not a recognized video file (mp4, mkv, mov). Download aborted.")
    except RequestException as e:
        print(f"Request failed: {e}")

def download_youtube_video(video_url, destination, cookies_file=None):
    """
    Downloads a YouTube video using yt-dlp with authentication via cookies.txt.
    
    Args:
        video_url (str): URL of the YouTube video
        destination (str): Directory to save the video
        cookies_file (str, optional): Path to cookies file. If None, will search in multiple locations.
    """
    try:
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
            print("Warning: No cookies.txt file found in any of these locations:")
            for loc in cookies_locations:
                print(f"  - {loc}")
            print("\nAttempting to download without cookies (may fail for age-restricted or private videos)...")
        
        print(f"\nDownloading YouTube video from: {video_url}")
        
        # Try using subprocess approach first (more reliable)
        try:
            cmd = ["yt-dlp"]
            if cookies_path:
                cmd.extend(["--cookies", cookies_path])
            cmd.extend([
                "-f", "bestvideo*+bestaudio/best",
                "-o", os.path.join(destination, "%(title)s.%(ext)s"),
                "--no-playlist",
                video_url
            ])
            
            print(f"Running command: {' '.join(cmd)}")
            subprocess.run(cmd, check=True)
            print(f"Download completed successfully!")
            return
            
        except subprocess.SubprocessError as e:
            print(f"Subprocess download failed: {e}")
            print("Falling back to yt-dlp Python API...")
        
        # Fall back to yt-dlp Python API if subprocess approach fails
        ydl_opts = {
            'outtmpl': os.path.join(destination, '%(title)s.%(ext)s'),
            'format': 'bestvideo*+bestaudio/best',
            'noplaylist': True,
            'progress_hooks': [progress_hook],
        }
        
        if cookies_path:
            ydl_opts['cookies'] = cookies_path
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        
        print(f"Download completed successfully!")

    except Exception as e:
        print(f"Failed to download YouTube video: {e}")

def progress_hook(d):
    """
    Progress hook function for yt-dlp.
    """
    if d['status'] == 'downloading':
        print(f"\rDownloading: {d['_percent_str']} ({d['_eta_str']} remaining)", end='')
    elif d['status'] == 'finished':
        print("\nDownload complete!")

def extract_video_url(url):
    try:
        # Send a GET request to the URL
        response = requests.get(url)
        
        # Parse the HTML content
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Check for video-wrapper iframe
        video_wrapper = soup.find(class_='video-wrapper')
        iframe = video_wrapper.find('iframe') if video_wrapper else None
        
        if iframe and 'src' in iframe.attrs:
            src = iframe['src']
            parsed_src = urlparse.urlparse(src)
            query_v = parse_qs(parsed_src.query).get('v')
            
            if query_v:
                youtube_url = f"https://www.youtube.com/watch?v={query_v[0]}"
                print(f"Found YouTube video: {youtube_url}")
                return youtube_url
            return src
        
        # Check for YouTube embedded video
        youtube_video = soup.find('iframe', src=lambda x: x and "youtube.com" in x)
        if youtube_video and 'src' in youtube_video.attrs:
            src = youtube_video['src']
            
            # Convert embed URLs to watch URLs
            if '/embed/' in src:
                video_id = src.split('/embed/')[1].split('?')[0]
                youtube_url = f"https://www.youtube.com/watch?v={video_id}"
                print(f"Found YouTube embed: {youtube_url}")
                return youtube_url
            
            print(f"Found YouTube iframe: {src}")
            return src
        
        # Check for Flowplayer embedded video
        flowplayer_div = soup.find('div', class_='flowplayer')
        if flowplayer_div and 'data-item' in flowplayer_div.attrs:
            data_item = flowplayer_div['data-item']
            data = json.loads(data_item)
            
            if 'sources' in data and data['sources']:
                video_url = data['sources'][0]['src']
                print(f"Flowplayer video found: {video_url}")
                return video_url
        
        # Check direct <video> tags
        video_tag = soup.find('video')
        if video_tag and video_tag.find('source'):
            source = video_tag.find('source')
            if 'src' in source.attrs:
                video_url = source['src']
                print(f"Direct video source found: {video_url}")
                return video_url
                
        # Check for direct YouTube links in the page
        youtube_links = soup.find_all('a', href=lambda x: x and ("youtube.com/watch" in x or "youtu.be/" in x))
        if youtube_links:
            youtube_url = youtube_links[0]['href']
            print(f"Found YouTube link: {youtube_url}")
            return youtube_url
        
        return None
        
    except Exception as e:
        print(f"Error extracting video URL: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Extract and download video URL from a webpage.")
    parser.add_argument('--source', '-s', type=str, help="The URL of the webpage to parse.")
    parser.add_argument('--destination', '-d', type=str, default=os.getcwd(), help="The destination directory to download the video. Default is the current directory.")
    parser.add_argument('--cookies', '-c', type=str, help="Path to cookies.txt file. If not specified, will search in script dir, current dir, and config dir.")
    parser.add_argument('--direct-youtube', '-y', action='store_true', help="Treat the source URL as a direct YouTube URL (skip extraction).")
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
        video_url = extract_video_url(args.source)
    
    if video_url:
        print(f"Video URL found: {video_url}")
        if "youtube.com" in video_url or "youtu.be" in video_url:
            download_youtube_video(video_url, args.destination, args.cookies)
        else:
            download_video(video_url, args.destination)
    else:
        print("No video URL found or the video URL does not contain a direct video link.")

if __name__ == "__main__":
    main()