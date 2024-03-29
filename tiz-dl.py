import requests
from bs4 import BeautifulSoup
import urllib.parse as urlparse
from urllib.parse import parse_qs, urlsplit
import argparse
import os
from requests.exceptions import RequestException
from tqdm import tqdm

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

def extract_video_url(url):
    # Send a GET request to the URL
    response = requests.get(url)
    
    # Parse the HTML content
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Find the element with class 'video-wrapper'
    video_wrapper = soup.find(class_='video-wrapper')
    
    # Find the first iframe inside that element
    iframe = video_wrapper.find('iframe') if video_wrapper else None
    
    if iframe and 'src' in iframe.attrs:
        src = iframe['src']
        
        # Parse the src URL to get the querystring value for 'v'
        parsed_src = urlparse.urlparse(src)
        query_v = parse_qs(parsed_src.query).get('v')
        
        if query_v:
            # Return the first 'v' parameter value if available
            return query_v[0]
    else:
        # If no iframe found in video-wrapper, check for YouTube embedded video
        youtube_video = soup.find('iframe', src=lambda x: x and "youtube.com" in x)
        if youtube_video and 'src' in youtube_video.attrs:
            print("Note: A YouTube embedded video was found instead of a direct video file.")
            return youtube_video['src']
            
    return None

def main():
    # Create the parser
    parser = argparse.ArgumentParser(description="Extract and download video URL from a webpage.")
    
    # Add the arguments
    parser.add_argument('--source', '-s', type=str, required=True, help="The URL of the webpage to parse.")
    parser.add_argument('--destination', '-d', type=str, default=os.getcwd(), help="The destination directory to download the video. Default is the current directory.")
    
    # Parse the command line arguments
    args = parser.parse_args()
    
    # Ensure destination directory exists
    if not os.path.isdir(args.destination):
        print(f"Creating directory: {args.destination}")
        os.makedirs(args.destination)
    
    # Extract the video URL
    video_url = extract_video_url(args.source)
    
    if video_url:
        print(f"Video URL found: {video_url}")
        if "youtube.com" in video_url:
            print("This is a YouTube video URL, download skipped.")
        else:
            download_video(video_url, args.destination)
    else:
        print("No video URL found or the video URL does not contain a direct video link.")

if __name__ == "__main__":
    main()
