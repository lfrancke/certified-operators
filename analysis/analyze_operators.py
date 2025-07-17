#!/usr/bin/env python3
"""
Comprehensive analysis script for certified-operators repository
Analyzes all operators to extract:
- Last update time for each operator
- OpenShift versions supported from annotations
- All relevant metadata
"""

import os
import yaml
import json
import datetime
import sys
from pathlib import Path
import re
from collections import defaultdict
import argparse
import subprocess

def parse_openshift_versions(version_str):
    """Parse OpenShift versions according to official Red Hat documentation
    
    Rules:
    - "v4.5" means supported on 4.5 and ALL subsequent versions
    - "=v4.6" means supported ONLY on 4.6
    - "v4.5-v4.7" means supported on 4.5, 4.6, and 4.7 (inclusive range)
    """
    if not version_str:
        return []
    
    # Remove quotes and whitespace
    version_str = version_str.strip(' "\'')
    
    versions = []
    
    # Split by comma first to handle mixed formats like "v4.8,v4.10-v4.12,v4.15"
    parts = [part.strip() for part in version_str.split(',')]
    
    for part in parts:
        if not part:
            continue
            
        # Handle range format: v4.11-v4.18 (inclusive range)
        range_match = re.match(r'v(\d+)\.(\d+)-v(\d+)\.(\d+)', part)
        if range_match:
            start_major, start_minor = int(range_match.group(1)), int(range_match.group(2))
            end_major, end_minor = int(range_match.group(3)), int(range_match.group(4))
            
            # Generate all versions in range (inclusive)
            current_major, current_minor = start_major, start_minor
            while current_major < end_major or (current_major == end_major and current_minor <= end_minor):
                versions.append(f"v{current_major}.{current_minor}")
                current_minor += 1
                if current_minor > 99:  # Safety check
                    break
                    
            continue
        
        # Handle exact version: =v4.12 (only that version)
        exact_match = re.match(r'=v(\d+)\.(\d+)', part)
        if exact_match:
            versions.append(f"v{exact_match.group(1)}.{exact_match.group(2)}")
            continue
        
        # Handle single version: v4.12 (this version and all subsequent)
        single_match = re.match(r'v(\d+)\.(\d+)', part)
        if single_match:
            major, minor = int(single_match.group(1)), int(single_match.group(2))
            
            # Add this version and all subsequent versions up to a reasonable limit
            # Based on current OpenShift release cycle, go up to v4.20
            current_major, current_minor = major, minor
            while current_major <= 4 and current_minor <= 20:
                versions.append(f"v{current_major}.{current_minor}")
                current_minor += 1
                if current_minor > 20:
                    current_major += 1
                    current_minor = 0
                    if current_major > 4:
                        break
            continue
        
        # Default: return as-is if it looks like a version
        if part.startswith('v'):
            versions.append(part)
    
    return versions

def analyze_version_type(version_str):
    """Analyze version specification type according to Red Hat policy
    
    Returns:
    - 'open_ended': versions like "v4.8" that apply to all subsequent versions
    - 'explicit': versions like "=v4.8" that apply only to specific version
    - 'ranged': versions like "v4.8-v4.12" that apply to inclusive range
    - 'mixed': contains multiple types
    """
    if not version_str:
        return 'none'
    
    # Remove quotes and whitespace
    version_str = version_str.strip(' "\'')
    
    # Split by comma to handle mixed formats
    parts = [part.strip() for part in version_str.split(',')]
    
    types_found = set()
    
    for part in parts:
        if not part:
            continue
            
        # Check for range format: v4.11-v4.18
        if re.match(r'v(\d+)\.(\d+)-v(\d+)\.(\d+)', part):
            types_found.add('ranged')
            continue
        
        # Check for explicit format: =v4.12
        if re.match(r'=v(\d+)\.(\d+)', part):
            types_found.add('explicit')
            continue
        
        # Check for open-ended format: v4.12
        if re.match(r'v(\d+)\.(\d+)', part):
            types_found.add('open_ended')
            continue
    
    if len(types_found) == 0:
        return 'none'
    elif len(types_found) == 1:
        return list(types_found)[0]
    else:
        return 'mixed'

def calculate_certification_risk(operator_data):
    """Calculate certification risk based on Red Hat policy changes
    
    Red Hat policy: Operators with open-ended versions (like "v4.8") that haven't
    been updated in 12+ months will be dropped from v4.19 index.
    
    Returns risk level: 'high', 'medium', 'low', 'none'
    """
    if not operator_data.get('last_update'):
        return 'unknown'
    
    # Parse last update date
    try:
        last_update = datetime.datetime.fromisoformat(operator_data['last_update'].replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        return 'unknown'
    
    # Calculate months since last update
    now = datetime.datetime.now()
    months_since_update = (now - last_update).days / 30.44  # Average days per month
    
    # Check if operator has any open-ended versions
    has_open_ended = False
    has_only_explicit = True
    
    for version_info in operator_data.get('versions', []):
        openshift_versions_str = ''
        if version_info.get('annotations'):
            openshift_versions_str = version_info['annotations'].get('com.redhat.openshift.versions', '')
        
        version_type = analyze_version_type(openshift_versions_str)
        
        if version_type in ['open_ended', 'mixed']:
            has_open_ended = True
            has_only_explicit = False
        elif version_type in ['ranged']:
            has_only_explicit = False
    
    # Apply Red Hat policy risk assessment
    if has_open_ended and months_since_update >= 12:
        return 'high'  # Will be dropped from v4.19 index
    elif has_open_ended and months_since_update >= 9:
        return 'medium'  # Approaching 12-month threshold
    elif has_open_ended and months_since_update >= 6:
        return 'low'  # May need attention soon
    else:
        return 'none'  # No risk or uses explicit/ranged versioning

def analyze_fbc_catalogs(operator_path):
    """Analyze FBC (File-Based Catalog) templates if they exist"""
    catalog_templates_path = os.path.join(operator_path, 'catalog-templates')
    
    if not os.path.exists(catalog_templates_path):
        return None
    
    fbc_data = {
        'has_fbc': True,
        'openshift_versions': [],
        'catalog_files': []
    }
    
    # Find all YAML files in catalog-templates
    try:
        for file in os.listdir(catalog_templates_path):
            if file.endswith('.yaml') or file.endswith('.yml'):
                file_path = os.path.join(catalog_templates_path, file)
                # Extract OpenShift version from filename (e.g., v4.12.yaml -> v4.12)
                version_match = re.match(r'v(\d+\.\d+)\.ya?ml', file)
                if version_match:
                    version = f"v{version_match.group(1)}"
                    fbc_data['openshift_versions'].append(version)
                    fbc_data['catalog_files'].append(file)
    except Exception as e:
        print(f"Error reading FBC catalog templates in {operator_path}: {e}")
    
    # Sort versions
    fbc_data['openshift_versions'] = sorted(list(set(fbc_data['openshift_versions'])))
    
    return fbc_data

def get_git_last_commit_time(directory):
    """Get the last commit time for a directory using git log"""
    try:
        # Use git log to get the last commit that modified this directory
        cmd = [
            'git', 'log', '-n' '1', '--format=%ct', '--', directory
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        if result.stdout.strip():
            # Convert unix timestamp to datetime
            timestamp = int(result.stdout.strip())
            return datetime.datetime.fromtimestamp(timestamp)
        
        return None
        
    except (subprocess.CalledProcessError, ValueError, OSError) as e:
        return None

def analyze_operator(operator_path):
    """Analyze a single operator directory"""
    operator_name = os.path.basename(operator_path)
    result = {
        'name': operator_name,
        'path': operator_path,
        'versions': [],
        'latest_version': None,
        'openshift_versions': [],
        'all_openshift_versions': [],
        'last_update': None,
        'total_versions': 0,
        'has_ci_yaml': False,
        'has_makefile': False,
        'error': None
    }
    
    try:
        # Check for ci.yaml and Makefile
        result['has_ci_yaml'] = os.path.exists(os.path.join(operator_path, 'ci.yaml'))
        result['has_makefile'] = os.path.exists(os.path.join(operator_path, 'Makefile'))
        
        # Get git last commit time for this directory
        last_update = get_git_last_commit_time(operator_path)
        if last_update:
            result['last_update'] = last_update.isoformat()
        
        # Check for FBC (File-Based Catalog) support
        fbc_data = analyze_fbc_catalogs(operator_path)
        if fbc_data:
            result['fbc'] = fbc_data
        
        # Find all version directories
        version_dirs = []
        for item in os.listdir(operator_path):
            version_path = os.path.join(operator_path, item)
            if os.path.isdir(version_path) and item not in ['catalog-templates', 'tests']:
                # Check if it has the expected structure (metadata/annotations.yaml)
                annotations_path = os.path.join(version_path, 'metadata', 'annotations.yaml')
                if os.path.exists(annotations_path):
                    version_dirs.append((item, version_path, annotations_path))
        
        result['total_versions'] = len(version_dirs)
        
        # Sort versions (attempt semantic versioning)
        def version_key(v):
            # Extract version components for sorting
            version_str = v[0]
            # Remove 'v' prefix and handle various formats
            clean_version = re.sub(r'^v', '', version_str)
            parts = re.split(r'[-.]', clean_version)
            
            # Convert to consistent types for comparison
            numeric_parts = []
            for part in parts:
                try:
                    # Try to convert to integer
                    numeric_parts.append((0, int(part)))  # (type, value) - 0 for numbers
                except ValueError:
                    # Keep as string with different type marker
                    numeric_parts.append((1, part))  # (type, value) - 1 for strings
            
            return numeric_parts
        
        version_dirs.sort(key=version_key)
        
        # Analyze each version
        for version, version_path, annotations_path in version_dirs:
            version_info = {
                'version': version,
                'path': version_path,
                'openshift_versions': [],
                'annotations': {}
            }
            
            try:
                with open(annotations_path, 'r') as f:
                    annotations_data = yaml.safe_load(f)
                    
                if annotations_data and 'annotations' in annotations_data:
                    annotations = annotations_data['annotations']
                    version_info['annotations'] = annotations
                    
                    # Extract OpenShift versions
                    openshift_versions_str = annotations.get('com.redhat.openshift.versions', '')
                    if openshift_versions_str:
                        openshift_versions = parse_openshift_versions(openshift_versions_str)
                        version_info['openshift_versions'] = openshift_versions
                        # Use set for deduplication, then convert to list
                        current_versions = set(result['openshift_versions'])
                        current_versions.update(openshift_versions)
                        result['openshift_versions'] = list(current_versions)
                        result['all_openshift_versions'].extend(openshift_versions)
                        
            except Exception as e:
                version_info['error'] = str(e)
            
            result['versions'].append(version_info)
        
        # Set latest version
        if version_dirs:
            result['latest_version'] = version_dirs[-1][0]
        
        # Convert to sorted list
        result['openshift_versions'] = sorted(result['openshift_versions'])
        
        # Add certification risk analysis
        result['certification_risk'] = calculate_certification_risk(result)
        
        # Analyze version types across all versions
        if result['versions']:
            version_types_found = set()
            for version_info in result['versions']:
                annotations = version_info.get('annotations', {})
                if isinstance(annotations, dict):
                    openshift_versions_str = annotations.get('com.redhat.openshift.versions', '')
                    version_type = analyze_version_type(openshift_versions_str)
                    if version_type != 'none':
                        version_types_found.add(version_type)
            
            # Determine overall version type
            if len(version_types_found) == 0:
                result['version_type'] = 'none'
            elif len(version_types_found) == 1:
                result['version_type'] = list(version_types_found)[0]
            else:
                result['version_type'] = 'mixed'
        else:
            result['version_type'] = 'none'
        
    except Exception as e:
        result['error'] = str(e)
    
    return result

def main():
    parser = argparse.ArgumentParser(description='Analyze certified operators')
    parser.add_argument('--output', '-o', default='operator_analysis.json', help='Output file path')
    parser.add_argument('--format', '-f', choices=['json', 'csv', 'summary'], default='json', help='Output format')
    parser.add_argument('--operators-dir', '-d', default='operators', help='Operators directory path')
    parser.add_argument('--filter', help='Filter operators by name (regex)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    operators_dir = args.operators_dir
    if not os.path.exists(operators_dir):
        print(f"Error: Directory {operators_dir} does not exist")
        sys.exit(1)
    
    # Get all operator directories
    operator_dirs = []
    for item in os.listdir(operators_dir):
        item_path = os.path.join(operators_dir, item)
        if os.path.isdir(item_path) and not item.startswith('.'):
            # Apply filter if specified
            if args.filter:
                if not re.search(args.filter, item):
                    continue
            operator_dirs.append(item_path)
    
    print(f"Found {len(operator_dirs)} operators to analyze")
    
    # Analyze all operators
    results = []
    errors = []
    
    for i, operator_path in enumerate(operator_dirs):
        if args.verbose:
            print(f"Analyzing {i+1}/{len(operator_dirs)}: {os.path.basename(operator_path)}")
        
        result = analyze_operator(operator_path)
        results.append(result)
        
        if result['error']:
            errors.append(result)
    
    # Generate summary statistics
    total_operators = len(results)
    total_versions = sum(r['total_versions'] for r in results)
    operators_with_versions = sum(1 for r in results if r['total_versions'] > 0)
    
    # FBC statistics
    fbc_operators = sum(1 for r in results if r.get('fbc'))
    fbc_openshift_versions = defaultdict(int)
    
    for result in results:
        if result.get('fbc'):
            for version in result['fbc']['openshift_versions']:
                fbc_openshift_versions[version] += 1
    
    # OpenShift version statistics
    all_openshift_versions = set()
    openshift_version_counts = defaultdict(int)
    
    for result in results:
        for version in result['openshift_versions']:
            all_openshift_versions.add(version)
            openshift_version_counts[version] += 1
    
    # Certification risk statistics
    risk_counts = defaultdict(int)
    version_type_counts = defaultdict(int)
    
    for result in results:
        risk_level = result.get('certification_risk', 'unknown')
        risk_counts[risk_level] += 1
        
        version_type = result.get('version_type', 'none')
        version_type_counts[version_type] += 1
    
    # Calculate Red Hat policy affected operators
    high_risk_operators = [r for r in results if r.get('certification_risk') == 'high']
    operators_at_risk = len(high_risk_operators)
    
    summary = {
        'analysis_timestamp': datetime.datetime.now().isoformat(),
        'total_operators': total_operators,
        'total_versions': total_versions,
        'operators_with_versions': operators_with_versions,
        'operators_without_versions': total_operators - operators_with_versions,
        'all_openshift_versions': sorted(list(all_openshift_versions)),
        'openshift_version_counts': dict(openshift_version_counts),
        'fbc_operators': fbc_operators,
        'fbc_openshift_version_counts': dict(fbc_openshift_versions),
        'certification_risk_counts': dict(risk_counts),
        'version_type_counts': dict(version_type_counts),
        'operators_at_risk': operators_at_risk,
        'errors': len(errors)
    }
    
    # Output results
    if args.format == 'json':
        output_data = {
            'summary': summary,
            'operators': results
        }
        
        with open(args.output, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        print(f"Results written to {args.output}")
    
    elif args.format == 'csv':
        import csv
        
        with open(args.output, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'operator_name', 'total_versions', 'latest_version', 
                'openshift_versions', 'last_update', 'certification_risk',
                'version_type', 'has_ci_yaml', 'has_makefile', 'error'
            ])
            
            for result in results:
                writer.writerow([
                    result['name'],
                    result['total_versions'],
                    result['latest_version'],
                    ','.join(result['openshift_versions']),
                    result['last_update'],
                    result.get('certification_risk', 'unknown'),
                    result.get('version_type', 'none'),
                    result['has_ci_yaml'],
                    result['has_makefile'],
                    result['error'] or ''
                ])
        
        print(f"CSV results written to {args.output}")
    
    elif args.format == 'summary':
        print("\n=== OPERATOR ANALYSIS SUMMARY ===")
        print(f"Total operators: {summary['total_operators']}")
        print(f"Total versions: {summary['total_versions']}")
        print(f"Operators with versions: {summary['operators_with_versions']}")
        print(f"Operators without versions: {summary['operators_without_versions']}")
        print(f"Analysis errors: {summary['errors']}")
        
        print(f"\nOpenShift versions found: {len(summary['all_openshift_versions'])}")
        for version in summary['all_openshift_versions']:
            count = summary['openshift_version_counts'][version]
            print(f"  {version}: {count} operators")
        
        print(f"\nCertification Risk Analysis:")
        print(f"  High risk operators (will be dropped from v4.19): {summary['operators_at_risk']}")
        for risk_level, count in summary['certification_risk_counts'].items():
            print(f"  {risk_level.title()} risk: {count} operators")
        
        print(f"\nVersion Type Distribution:")
        for version_type, count in summary['version_type_counts'].items():
            print(f"  {version_type.replace('_', ' ').title()}: {count} operators")
        
        if summary['operators_at_risk'] > 0:
            print(f"\nHigh Risk Operators (Red Hat Policy Affected):")
            for op in high_risk_operators[:10]:  # Show first 10 high-risk operators
                print(f"  {op['name']}: {op['last_update']} ({op.get('version_type', 'unknown')} versioning)")
        
        print(f"\nTop 10 most recently updated operators:")
        sorted_operators = sorted(
            [r for r in results if r['last_update']], 
            key=lambda x: x['last_update'], 
            reverse=True
        )[:10]
        
        for op in sorted_operators:
            print(f"  {op['name']}: {op['last_update']}")
    
    # Print summary to console regardless of format
    print(f"\nSummary: {summary['total_operators']} operators, {summary['total_versions']} versions")
    if errors:
        print(f"Errors encountered: {len(errors)}")
        for error in errors[:5]:  # Show first 5 errors
            print(f"  {error['name']}: {error['error']}")

if __name__ == '__main__':
    main()
