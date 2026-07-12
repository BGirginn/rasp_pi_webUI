#!/bin/bash
# Upload a file to the Raspberry Pi
# Usage: ./upload_to_pi.sh <local_file_path> [remote_directory]

# Configuration
PI_USER="fou4"
PI_HOST="192.168.1.180"
DEFAULT_REMOTE_DIR="/home/fou4"

# Check arguments
if [ -z "$1" ]; then
    echo "Usage: $0 <local_file> [remote_directory]"
    echo "Example: $0 ./my-image.png /home/fou4/Downloads"
    echo ""
    exit 1
fi

LOCAL_FILE="$1"
REMOTE_DIR="${2:-$DEFAULT_REMOTE_DIR}"

# Check if file exists
if [ ! -f "$LOCAL_FILE" ]; then
    echo "Error: File '$LOCAL_FILE' not found!"
    exit 1
fi

echo "🚀 Uploading '$LOCAL_FILE' to '$REMOTE_DIR' on $PI_USER@$PI_HOST..."

# Execute SCP command
scp "$LOCAL_FILE" "${PI_USER}@${PI_HOST}:${REMOTE_DIR}/"

if [ $? -eq 0 ]; then
    echo "✅ Upload successful!"
else
    echo "❌ Upload failed!"
fi
