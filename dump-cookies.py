#!/usr/bin/env python3
"""
yt-dlp-cookie-saver.py - Script to save browser cookies for yt-dlp

This script uses the browser_cookies3 module to extract cookies directly
without relying on yt-dlp's --dump-cookies option.
"""

import os
import argparse
import sys
import json
from pathlib import Path

# Note: You'll need to install the browser_cookies3 module:
# pip install browser-cookie3

def save_cookies(browser_name, cookie_file):
    """Extract cookies from browser and save to file."""
    try:
        # Dynamic import so the script doesn't fail if the module isn't installed
        import browser_cookie3
    except ImportError:
        print("Error: browser_cookie3 module not found.")
        print("Please install it using: pip install browser-cookie3")
        return False

    # Map browser names to browser_cookie3 functions
    browser_functions = {
        "chrome": browser_cookie3.chrome,
        "firefox": browser_cookie3.firefox,
        "opera": browser_cookie3.opera,
        "edge": browser_cookie3.edge,
        "chromium": browser_cookie3.chromium,
        "brave": browser_cookie3.brave,
        "vivaldi": browser_cookie3.vivaldi,
        "safari": browser_cookie3.safari
    }

    if browser_name not in browser_functions:
        print(f"Error: Browser '{browser_name}' not supported.")
        return False

    try:
        # Get cookies from the browser
        cj = browser_functions[browser_name]()
        
        # Create directory for cookie file if needed
        cookie_dir = os.path.dirname(cookie_file)
        if cookie_dir:
            os.makedirs(cookie_dir, exist_ok=True)
        
        # Filter for only YouTube cookies
        with open(cookie_file, 'w') as f:
            f.write("# Netscape HTTP Cookie File\n")
            f.write("# This file was generated by yt-dlp-cookie-saver.py\n\n")
            
            for cookie in cj:
                if ".youtube.com" in cookie.domain:
                    domain = cookie.domain if cookie.domain.startswith('.') else '.' + cookie.domain
                    secure = "TRUE" if cookie.secure else "FALSE"
                    http_only = "TRUE" if cookie.has_nonstandard_attr('HttpOnly') else "FALSE"
                    expires = int(cookie.expires) if cookie.expires else 0
                    
                    f.write(f"{domain}\tTRUE\t{cookie.path}\t{secure}\t{expires}\t{cookie.name}\t{cookie.value}\n")
        
        if os.path.exists(cookie_file) and os.path.getsize(cookie_file) > 0:
            print(f"Cookies successfully saved to {cookie_file}")
            return True
        else:
            print("Cookie file was created but appears to be empty.")
            return False
            
    except Exception as e:
        print(f"Error extracting cookies: {e}")
        return False

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Save browser cookies for use with yt-dlp")
    
    parser.add_argument(
        "browser",
        nargs="?",
        choices=["chrome", "firefox", "safari", "edge", "opera", "brave", "vivaldi", "chromium"],
        default="chrome",
        help="Browser to extract cookies from (default: chrome)"
    )
    
    parser.add_argument(
        "--output", "-o",
        default="cookies.txt",
        help="Path to save cookies file (default: ./cookies.txt in current directory)"
    )
    
    args = parser.parse_args()
    
    # Save the cookies
    if save_cookies(args.browser, args.output):
        print(f"\nTo use these cookies with yt-dlp, run:")
        print(f"yt-dlp --cookies {args.output} [URL]")
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()