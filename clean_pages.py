#!/usr/bin/env python3
"""Clean MDX pages - remove Badges, Cards, keep verbatim statute text."""

import re
import os
import subprocess

def clean_mdx(content):
    # Remove Badge components
    content = re.sub(r'<Badge[^>]*>.*?</Badge>', '', content)
    content = re.sub(r'<Badge[^>]*/>', '', content)
    
    # Remove Card, CardGroup, Columns, Note components (keep children)
    content = re.sub(r'</?(CardGroup|Columns|Note|Card|AccordionGroup|Accordion|Tabs|Tab|Steps|Step)[^>]*>', '', content)
    
    # Remove className="statute-card" wrapper divs but keep content
    content = re.sub(r'<div className="statute-card">\s*', '', content)
    content = re.sub(r'<div className="section-body">\s*', '', content)
    content = re.sub(r'<div className="section-meta">\s*', '', content)
    content = re.sub(r'\s*</div>\s*', '\n', content)
    
    # Clean up extra blank lines
    content = re.sub(r'\n{4,}', '\n\n\n', content)
    
    return content.strip() + '\n'

def main():
    pages_dir = '/Users/2024-jan/f/family-x1oh1xy2/fern/docs/pages'
    
    for fname in os.listdir(pages_dir):
        if not fname.endswith('.mdx'):
            continue
        path = os.path.join(pages_dir, fname)
        
        # Get original from git
        try:
            result = subprocess.run(['git', 'show', f'HEAD:{fname}'], 
                                  cwd='/Users/2024-jan/f/family-x1oh1xy2',
                                  capture_output=True, text=True)
            if result.returncode == 0:
                original = result.stdout
            else:
                with open(path) as f:
                    original = f.read()
        except:
            with open(path) as f:
                original = f.read()
        
        cleaned = clean_mdx(original)
        
        with open(path, 'w') as f:
            f.write(cleaned)
        
        print(f'Cleaned: {fname}')

    print('Done!')