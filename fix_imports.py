#!/usr/bin/env python3
"""Fix incorrect MCP imports in large services"""

import re
from pathlib import Path

def fix_service_imports(filepath):
    """Remove non-existent MCP imports"""
    print(f"Fixing {filepath.name}...")
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Remove non-existent imports
    replacements = [
        # Remove ResourceParams, ToolParams - they don't exist
        (r'from mcp\.server\.fastmcp import FastMCP, ResourceParams, ToolParams',
         'from mcp.server.fastmcp import FastMCP'),
        (r', ResourceParams, ToolParams', ''),
        (r', ResourceParams', ''),
        (r', ToolParams', ''),
        
        # Remove non-existent response types
        (r'from mcp import ResourceResponse, ToolResponse, MCPError.*\n', ''),
        (r'import.*ResourceResponse.*\n', ''),
        (r'import.*ToolResponse.*\n', ''),
        
        # Fix return type hints that use these
        (r'-> ResourceResponse', '-> Dict'),
        (r'-> ToolResponse', '-> Dict'),
    ]
    
    for pattern, replacement in replacements:
        content = re.sub(pattern, replacement, content)
    
    # Add Dict import if needed
    if '-> Dict' in content and 'from typing import' not in content:
        content = 'from typing import Dict, List, Optional, Any\n' + content
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"  ✓ Fixed imports in {filepath.name}")

# Fix each large service
services = [
    'services/news/news-service.py',
    'services/scanner/scanner-service.py',
    'services/pattern/pattern-service.py',
    'services/technical/technical-service.py',
    'services/trading/trading-service.py'
]

for service_path in services:
    filepath = Path(service_path)
    if filepath.exists():
        fix_service_imports(filepath)

print("\n✅ Import fixes complete!")
