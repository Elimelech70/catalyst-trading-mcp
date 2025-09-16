#!/usr/bin/env python3
"""
GitHub Repository Indexer for Claude
Creates a comprehensive index of all files in your repositories with direct raw URLs
Run from VSCode terminal: python repo_indexer.py
"""

import os
import json
from datetime import datetime
from pathlib import Path
import subprocess

# Configuration
REPOS = [
    {
        "name": "Conversations-with-Claude",
        "url": "https://github.com/Elimelech70/Conversations-with-Claude",
        "local_path": "./Conversations-with-Claude"
    },
    {
        "name": "catalyst-trading-mcp",
        "url": "https://github.com/Elimelech70/catalyst-trading-mcp",
        "local_path": "./catalyst-trading-mcp"
    }
]

def clone_or_pull_repo(repo):
    """Clone repository if it doesn't exist, otherwise pull latest changes"""
    if os.path.exists(repo["local_path"]):
        print(f"📂 Updating {repo['name']}...")
        subprocess.run(["git", "-C", repo["local_path"], "pull"], check=True)
    else:
        print(f"📥 Cloning {repo['name']}...")
        subprocess.run(["git", "clone", repo["url"], repo["local_path"]], check=True)

def get_file_content_preview(file_path, lines=5):
    """Get first few lines of a file for context"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.readlines()[:lines]
            return ''.join(content).strip()
    except:
        return "Binary or unreadable file"

def index_repository(repo):
    """Create an index of all files in the repository"""
    repo_index = {
        "name": repo["name"],
        "url": repo["url"],
        "files": [],
        "structure": {}
    }
    
    # Walk through repository
    for root, dirs, files in os.walk(repo["local_path"]):
        # Skip .git directory
        if '.git' in root:
            continue
            
        for file in files:
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, repo["local_path"])
            
            # Create raw GitHub URL
            raw_url = f"https://raw.githubusercontent.com/Elimelech70/{repo['name']}/main/{relative_path.replace(os.sep, '/')}"
            
            file_info = {
                "path": relative_path,
                "name": file,
                "raw_url": raw_url,
                "extension": Path(file).suffix,
                "size": os.path.getsize(file_path),
                "preview": get_file_content_preview(file_path, 3)
            }
            
            repo_index["files"].append(file_info)
    
    return repo_index

def create_markdown_index(all_repos_index):
    """Create a comprehensive markdown file with all repository contents"""
    md_content = f"""# Complete Repository Index for Claude
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Quick Instructions for Claude
1. This file contains direct raw URLs to all files in Craig's repositories
2. You can fetch any file by copying its raw URL
3. Files are organized by repository and file type

---

"""
    
    for repo_index in all_repos_index:
        md_content += f"## 📁 Repository: {repo_index['name']}\n"
        md_content += f"GitHub: {repo_index['url']}\n\n"
        
        # Group files by extension
        files_by_type = {}
        for file in repo_index['files']:
            ext = file['extension'] if file['extension'] else 'no-extension'
            if ext not in files_by_type:
                files_by_type[ext] = []
            files_by_type[ext].append(file)
        
        # Write files grouped by type
        for ext, files in sorted(files_by_type.items()):
            md_content += f"### {ext} files\n"
            for file in files:
                md_content += f"- **{file['path']}**\n"
                md_content += f"  - URL: `{file['raw_url']}`\n"
                md_content += f"  - Size: {file['size']} bytes\n"
                if file['preview'] and len(file['preview']) > 0:
                    preview = file['preview'].replace('\n', '\n    ')
                    md_content += f"  - Preview:\n    ```\n    {preview}\n    ```\n"
                md_content += "\n"
        
        md_content += "---\n\n"
    
    return md_content

def create_json_index(all_repos_index):
    """Create a JSON file with all repository contents for programmatic access"""
    return json.dumps(all_repos_index, indent=2)

def main():
    """Main function to index all repositories"""
    print("🚀 Starting Repository Indexer for Claude\n")
    
    all_repos_index = []
    
    # Process each repository
    for repo in REPOS:
        print(f"\n📊 Processing {repo['name']}...")
        
        # Clone or update repo
        try:
            clone_or_pull_repo(repo)
        except Exception as e:
            print(f"❌ Error with {repo['name']}: {e}")
            continue
        
        # Index repository
        repo_index = index_repository(repo)
        all_repos_index.append(repo_index)
        print(f"✅ Indexed {len(repo_index['files'])} files")
    
    # Create output files
    print("\n📝 Creating index files...")
    
    # Create markdown index
    md_content = create_markdown_index(all_repos_index)
    md_filename = f"claude_index_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    with open(md_filename, 'w', encoding='utf-8') as f:
        f.write(md_content)
    print(f"✅ Created {md_filename}")
    
    # Create JSON index
    json_content = create_json_index(all_repos_index)
    json_filename = f"claude_index_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(json_filename, 'w', encoding='utf-8') as f:
        f.write(json_content)
    print(f"✅ Created {json_filename}")
    
    # Create a latest symlink for easy access
    latest_md = "claude_index_latest.md"
    latest_json = "claude_index_latest.json"
    
    # Remove old symlinks if they exist
    for f in [latest_md, latest_json]:
        if os.path.exists(f):
            os.remove(f)
    
    # Create new symlinks (Windows compatible)
    if os.name == 'nt':  # Windows
        os.system(f'copy "{md_filename}" "{latest_md}"')
        os.system(f'copy "{json_filename}" "{latest_json}"')
    else:  # Unix/Linux/Mac
        os.symlink(md_filename, latest_md)
        os.symlink(json_filename, latest_json)
    
    print(f"\n✨ Indexing complete!")
    print(f"📋 Share '{latest_md}' with Claude for easy file access")
    print(f"🔍 Total files indexed: {sum(len(r['files']) for r in all_repos_index)}")
    
    # Create a special Claude instruction file
    instruction_content = f"""# Claude Quick Start
    
## To access these files:
1. Craig will share this file URL with you
2. You can then fetch any file using the raw URLs listed
3. Focus on the most relevant files for the current conversation

## Repository URLs:
- Conversations: https://raw.githubusercontent.com/Elimelech70/Conversations-with-Claude/main/README.md
- Trading App: https://raw.githubusercontent.com/Elimelech70/catalyst-trading-mcp/main/README.md

## Index File:
- Full Index: {latest_md}

Generated: {datetime.now()}
"""
    
    with open("claude_instructions.md", 'w') as f:
        f.write(instruction_content)
    
    print(f"📌 Created 'claude_instructions.md' for quick reference")

if __name__ == "__main__":
    main()
