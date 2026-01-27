#!/usr/bin/env python3
"""
Google Drive Authentication Script for Pi Control Panel

This script handles the OAuth2 authentication flow for Google Drive API.
Run this script on the Pi to authenticate with your Google account.

Prerequisites:
1. Create OAuth 2.0 credentials at https://console.cloud.google.com/
2. Download the credentials JSON file
3. Rename it to 'gdrive_credentials.json' and place in /opt/pi-control/credentials/

Usage:
    python3 gdrive_auth.py

After running, follow the URL provided and paste the authorization code.
"""

import os
import sys
import json

# Add the panel/api to path for imports
sys.path.insert(0, '/opt/pi-control/panel/api')

CREDENTIALS_DIR = '/opt/pi-control/credentials'
CLIENT_SECRETS_FILE = os.path.join(CREDENTIALS_DIR, 'gdrive_credentials.json')
TOKEN_FILE = os.path.join(CREDENTIALS_DIR, 'gdrive_token.json')
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def main():
    print("=" * 60)
    print("  Google Drive Authentication for Pi Control Panel")
    print("=" * 60)
    print()
    
    # Check if client secrets exist
    if not os.path.exists(CLIENT_SECRETS_FILE):
        print("❌ ERROR: Client secrets file not found!")
        print()
        print("Please follow these steps:")
        print()
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create a new project (or select existing)")
        print("3. Enable the Google Drive API:")
        print("   - Go to 'APIs & Services' > 'Library'")
        print("   - Search for 'Google Drive API'")
        print("   - Click Enable")
        print()
        print("4. Create OAuth 2.0 credentials:")
        print("   - Go to 'APIs & Services' > 'Credentials'")
        print("   - Click 'Create Credentials' > 'OAuth client ID'")
        print("   - Select 'Desktop app' as application type")
        print("   - Download the JSON file")
        print()
        print("5. Copy the file to Pi:")
        print(f"   scp ~/Downloads/client_secret_*.json fou4@<pi-ip>:{CLIENT_SECRETS_FILE}")
        print()
        return 1
    
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.oauth2.credentials import Credentials
    except ImportError:
        print("❌ ERROR: Google libraries not installed!")
        print()
        print("Run: pip install google-auth-oauthlib google-api-python-client")
        return 1
    
    # Check if already authenticated
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
            if creds and creds.valid:
                print("✅ Already authenticated!")
                print(f"   Token file: {TOKEN_FILE}")
                print()
                print("To re-authenticate, delete the token file and run again:")
                print(f"   rm {TOKEN_FILE}")
                return 0
        except Exception:
            pass
    
    print("Starting OAuth2 authentication flow...")
    print()
    
    try:
        # Use out-of-band flow for headless Pi
        flow = InstalledAppFlow.from_client_secrets_file(
            CLIENT_SECRETS_FILE, 
            SCOPES,
            redirect_uri='urn:ietf:wg:oauth:2.0:oob'
        )
        
        # Generate authorization URL
        auth_url, _ = flow.authorization_url(prompt='consent')
        
        print("Please visit this URL to authorize the application:")
        print()
        print("-" * 60)
        print(auth_url)
        print("-" * 60)
        print()
        print("After authorizing, you will receive an authorization code.")
        print()
        
        code = input("Enter the authorization code: ").strip()
        
        if not code:
            print("❌ No code provided. Aborting.")
            return 1
        
        # Exchange code for tokens
        flow.fetch_token(code=code)
        creds = flow.credentials
        
        # Save the credentials
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
        
        print()
        print("✅ Authentication successful!")
        print(f"   Token saved to: {TOKEN_FILE}")
        print()
        print("Google Drive backup is now ready to use.")
        print("Restart the pi-control service to apply changes:")
        print("   sudo systemctl restart pi-control")
        print()
        
        return 0
        
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
