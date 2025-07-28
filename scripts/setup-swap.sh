#!/bin/bash

echo "=== Setting up swap space on production server ==="
echo "This will add 2GB of swap to prevent OOM issues"
echo ""

# Check if already has swap
EXISTING_SWAP=$(ssh root@129.212.136.218 "free -h | grep Swap | awk '{print \$2}'")

if [ "$EXISTING_SWAP" != "0B" ]; then
    echo "Server already has swap: $EXISTING_SWAP"
    echo "Exiting..."
    exit 0
fi

echo "No swap found. Creating 2GB swap file..."

ssh root@129.212.136.218 << 'EOF'
# Create swap file
echo "Creating swap file..."
fallocate -l 2G /swapfile

# Set permissions
chmod 600 /swapfile

# Make swap
echo "Setting up swap..."
mkswap /swapfile

# Enable swap
echo "Enabling swap..."
swapon /swapfile

# Make permanent
echo "Making swap permanent..."
echo '/swapfile none swap sw 0 0' >> /etc/fstab

# Verify
echo ""
echo "Swap setup complete!"
free -h
EOF

echo ""
echo "Done! The server now has swap space to handle memory spikes."