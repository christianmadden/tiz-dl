import requests
from bs4 import BeautifulSoup
import urllib.parse as urlparse
from urllib.parse import parse_qs, urlsplit
import argparse
import os
import json
from requests.exceptions import RequestException
from tqdm import tqdm
from pytube import YouTube

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

def download_youtube_video(video_url, destination):
    try:
        yt = YouTube(video_url)
        print(f"Downloading YouTube video: {yt.title}")
        stream = yt.streams.get_highest_resolution()
        stream.download(output_path=destination)
        print(f"Download completed: {stream.default_filename} in {destination}")
    except Exception as e:
        print(f"Failed to download YouTube video: {e}")

def extract_video_url(url):
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
            return query_v[0]
    
    # Check for YouTube embedded video
    youtube_video = soup.find('iframe', src=lambda x: x and "youtube.com" in x)
    if youtube_video and 'src' in youtube_video.attrs:
        print("Note: A YouTube embedded video was found.")
        return youtube_video['src']
    
    # Check for Flowplayer embedded video
    flowplayer_div = soup.find('div', class_='flowplayer')
    if flowplayer_div and 'data-item' in flowplayer_div.attrs:
        data_item = flowplayer_div['data-item']
        data = json.loads(data_item)
        
        if 'sources' in data and data['sources']:
            video_url = data['sources'][0]['src']
            print(f"Flowplayer video found: {video_url}")
            return video_url
    
    return None

def main():
    parser = argparse.ArgumentParser(description="Extract and download video URL from a webpage.")
    parser.add_argument('--source', '-s', type=str, required=True, help="The URL of the webpage to parse.")
    parser.add_argument('--destination', '-d', type=str, default=os.getcwd(), help="The destination directory to download the video. Default is the current directory.")
    args = parser.parse_args()
    
    # Ensure destination directory exists
    if not os.path.isdir(args.destination):
        print(f"Creating directory: {args.destination}")
        os.makedirs(args.destination)
    
    # Extract the video URL
    video_url = extract_video_url(args.source)
    
    if video_url:
        print(f"Video URL found: {video_url}")
        if "youtube.com" in video_url or "youtu.be" in video_url:
            download_youtube_video(video_url, args.destination)
        else:
            download_video(video_url, args.destination)
    else:
        print("No video URL found or the video URL does not contain a direct video link.")

if __name__ == "__main__":
    main()
