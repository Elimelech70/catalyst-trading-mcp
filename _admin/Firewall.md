# Block the Dashboard Port
bash
# Remove the allow rule for port 8080
ufw delete allow 8080/tcp

# Reload firewall
ufw reload

# Verify it's blocked
ufw status | grep 8080
# Should show nothing (port is now blocked)

# Enable Dashboard Access
bash
# Re-allow port 8080
ufw allow 8080/tcp

# Reload firewall  
ufw reload

# Verify it's open again
ufw status | grep 8080
# Should show: 8080/tcp  ALLOW  Anywhere