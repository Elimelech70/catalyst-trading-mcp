# Remove git and reinitialize
rm -rf .git
git init
git add -A
git commit -m "Initial commit - Complete MCP v3.0.0 implementation"
git branch -M main
git remote add origin https://github.com/Elimelech70/catalyst-trading-mcp.git
git push -u origin main --force
#Verify Everything Uploaded
#bash# Check that all files are tracked
git ls-files | sort