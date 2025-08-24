# SSH Setup Guide for DigitalOcean Droplet

**Name of Application:** Catalyst Trading System  
**Name of file:** ssh-setup-guide.md  
**Version:** 1.0.0  
**Last Updated:** 2025-01-27  
**Purpose:** Setup SSH access to DigitalOcean droplet from local laptop

**REVISION HISTORY:**
- v1.0.0 (2025-01-27) - Initial SSH setup guide
  - SSH key generation
  - DigitalOcean configuration
  - Connection testing
  - SSH config optimization

**Description of Service:**
Complete guide for setting up secure SSH access to your DigitalOcean droplet hosting the Catalyst Trading MCP system.

---

## Step 1: Generate SSH Key Pair on Your Laptop

Open Terminal on your laptop and run:

```bash
# Generate a new SSH key pair (recommended: ed25519 algorithm)
ssh-keygen -t ed25519 -C "catalyst-trading-mcp" -f ~/.ssh/catalyst_droplet


When prompted:
- Press Enter to accept the default location (or specify custom path)
- Enter a strong passphrase (recommended) or press Enter for no passphrase

## Step 2: Display Your Public Key

```bash
# Display the public key to copy
cat ~/.ssh/catalyst_droplet.pub
```
Copy the entire output (starts with `ssh-ed25519` or `ssh-rsa`)

## Step 3: Add SSH Key to DigitalOcean

### Option A: Via DigitalOcean Control Panel
1. Log into DigitalOcean Control Panel
2. Navigate to Settings → Security → SSH Keys
3. Click "Add SSH Key"
4. Paste your public key
5. Name it "Catalyst Trading Laptop"
6. Click "Add SSH Key"

### Option B: Add to Existing Droplet
If droplet already exists, add key directly:

```bash
# First, get your droplet's IP address from DigitalOcean panel
# Then use password authentication one time to add your key:

ssh root@YOUR_DROPLET_IP
# Enter root password when prompted

# Once logged in, add your public key:
echo "YOUR_PUBLIC_KEY_HERE" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
exit
```

## Step 4: Test SSH Connection

```bash
# Connect using your new SSH key
ssh -i ~/.ssh/catalyst_droplet root@YOUR_DROPLET_IP

# Example:
# ssh -i ~/.ssh/catalyst_droplet root@68.183.177.11
```

## Step 5: Create SSH Config for Easy Access

Create/edit `~/.ssh/config` file:

```bash
# Open SSH config file
nano ~/.ssh/config
```

Add this configuration:

```
Host catalyst-trading
    HostName YOUR_DROPLET_IP
    User root
    Port 22
    IdentityFile ~/.ssh/catalyst_droplet
    ServerAliveInterval 60
    ServerAliveCountMax 3
    TCPKeepAlive yes
```

Save and set proper permissions:

```bash
chmod 600 ~/.ssh/config
```

## Step 6: Connect Using Simple Alias

Now you can connect simply with:

```bash
ssh catalyst-trading
```

## Step 7: (Optional) Create Non-Root User

For better security, create a dedicated user:

```bash
# Connect as root first
ssh catalyst-trading

# Create new user
adduser catalyst
usermod -aG sudo catalyst

# Copy SSH keys to new user
rsync --archive --chown=catalyst:catalyst ~/.ssh /home/catalyst

# Test connection
exit
ssh catalyst@YOUR_DROPLET_IP -i ~/.ssh/catalyst_droplet
```

## Step 8: Secure Your Droplet

Once SSH key authentication works:

```bash
# Connect to droplet
ssh catalyst-trading

# Disable password authentication
sudo nano /etc/ssh/sshd_config

# Set these values:
# PasswordAuthentication no
# PubkeyAuthentication yes
# PermitRootLogin prohibit-password

# Restart SSH service
sudo systemctl restart sshd
```

## Troubleshooting Commands

```bash
# Check SSH key permissions
ls -la ~/.ssh/catalyst_droplet*

# Correct permissions if needed
chmod 600 ~/.ssh/catalyst_droplet
chmod 644 ~/.ssh/catalyst_droplet.pub

# Test connection with verbose output
ssh -vvv -i ~/.ssh/catalyst_droplet root@YOUR_DROPLET_IP

# Check SSH agent
ssh-add -l

# Add key to SSH agent
ssh-add ~/.ssh/catalyst_droplet

# Remove old host key if IP changed
ssh-keygen -R YOUR_DROPLET_IP
```

## Quick Reference

```bash
# Generate key
ssh-keygen -t ed25519 -f ~/.ssh/catalyst_droplet

# View public key
cat ~/.ssh/catalyst_droplet.pub

# Connect with key file
ssh -i ~/.ssh/catalyst_droplet root@68.183.177.11

# Connect with config alias
ssh catalyst-trading

# Copy files to droplet
scp file.txt catalyst-trading:/root/

# Copy files from droplet
scp catalyst-trading:/root/file.txt ./

# Port forwarding (access services locally)
ssh -L 5000:localhost:5000 catalyst-trading
```

## Next Steps

After SSH is configured:
1. Clone your Catalyst Trading MCP repository
2. Set up environment variables
3. Configure DigitalOcean managed database connection
4. Start Docker containers using manage.sh script

---

**Note:** Replace `YOUR_DROPLET_IP` with your actual DigitalOcean droplet IP address throughout these commands.