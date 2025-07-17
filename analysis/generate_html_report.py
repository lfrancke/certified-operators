#!/usr/bin/env python3
"""
Generate HTML report from operator analysis data
"""

import json
import sys
from datetime import datetime, timedelta
from collections import defaultdict

def load_analysis_data(json_file):
    """Load analysis data from JSON file"""
    with open(json_file, 'r') as f:
        return json.load(f)

def generate_html_report(data):
    """Generate HTML report from analysis data"""
    
    # Extract summary stats from data structure
    total_operators = data['summary']['total_operators']
    operators_with_versions = data['summary']['operators_with_versions']
    operators_without_versions = data['summary']['operators_without_versions']
    total_versions = data['summary']['total_versions']
    
    # FBC statistics
    fbc_operators = data['summary'].get('fbc_operators', 0)
    fbc_version_counts = data['summary'].get('fbc_openshift_version_counts', {})
    
    # Certification risk statistics
    risk_counts = data['summary'].get('certification_risk_counts', {})
    version_type_counts = data['summary'].get('version_type_counts', {})
    operators_at_risk = data['summary'].get('operators_at_risk', 0)
    
    # High risk operators for policy section
    high_risk_ops = sorted([op for op in data['operators'] if op.get('certification_risk') == 'high'], 
                          key=lambda x: x.get('last_update', ''), reverse=False)[:20]
    
    # OpenShift version stats from summary
    version_counts = data['summary']['openshift_version_counts']
    
    # Sort versions by count
    sorted_versions = sorted(version_counts.items(), key=lambda x: x[1], reverse=True)
    
    # Recent updates
    recent_ops = sorted([op for op in data['operators'] if op.get('last_update')], 
                       key=lambda x: x['last_update'], reverse=True)[:20]
    
    # Top operators by version count
    top_ops = sorted(data['operators'], key=lambda x: len(x.get('versions', [])), reverse=True)[:20]
    
    # Vendor analysis
    vendor_counts = defaultdict(int)
    for op in data['operators']:
        vendor = op['name'].split('-')[0]
        vendor_counts[vendor] += 1
    
    top_vendors = sorted(vendor_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    
    # Timeline analysis
    timeline_counts = defaultdict(int)
    for op in data['operators']:
        if op.get('last_update'):
            try:
                dt = datetime.fromisoformat(op['last_update'].replace('Z', '+00:00'))
                # Group by year and half-year
                year = dt.year
                half = "H1" if dt.month <= 6 else "H2"
                timeline_counts[f"{year}-{half}"] += 1
            except:
                pass
    
    sorted_timeline = sorted(timeline_counts.items(), key=lambda x: x[0], reverse=True)
    
    # Vendor freshness analysis
    vendor_freshness = defaultdict(lambda: {'count': 0, 'recent_updates': 0, 'avg_days_old': 0, 'total_days': 0})
    recent_cutoff = datetime.now() - timedelta(days=180)  # 6 months
    
    for op in data['operators']:
        vendor = op['name'].split('-')[0]
        vendor_freshness[vendor]['count'] += 1
        
        if op.get('last_update'):
            try:
                dt = datetime.fromisoformat(op['last_update'].replace('Z', '+00:00'))
                days_old = (datetime.now() - dt).days
                vendor_freshness[vendor]['total_days'] += days_old
                
                if dt > recent_cutoff:
                    vendor_freshness[vendor]['recent_updates'] += 1
            except:
                pass
    
    # Calculate averages and freshness metrics
    for vendor, stats in vendor_freshness.items():
        if stats['count'] > 0:
            stats['avg_days_old'] = stats['total_days'] / stats['count']
            stats['freshness_score'] = (stats['recent_updates'] / stats['count']) * 100
            stats['recent_percentage'] = (stats['recent_updates'] / stats['count']) * 100
    
    # Sort vendors by freshness score (recent updates percentage)
    fresh_vendors = sorted(
        [(vendor, stats) for vendor, stats in vendor_freshness.items() if stats['count'] >= 3],
        key=lambda x: x[1]['freshness_score'], reverse=True
    )[:15]
    
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Certified Operators Analysis Report</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
            color: #333;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 3px solid #3498db;
        }}
        h2 {{
            color: #34495e;
            margin-top: 40px;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #ecf0f1;
        }}
        h3 {{
            color: #2c3e50;
            margin-top: 30px;
            margin-bottom: 15px;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .stat-number {{
            font-size: 2.5em;
            font-weight: bold;
            margin-bottom: 10px;
        }}
        .stat-label {{
            font-size: 1.1em;
            opacity: 0.9;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 30px;
            background-color: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ecf0f1;
        }}
        th {{
            background-color: #34495e;
            color: white;
            font-weight: 600;
        }}
        tr:hover {{
            background-color: #f8f9fa;
        }}
        .chart-container {{
            margin: 20px 0;
            padding: 20px;
            background-color: #f8f9fa;
            border-radius: 8px;
            border: 1px solid #e9ecef;
        }}
        .bar {{
            display: flex;
            align-items: center;
            margin-bottom: 8px;
        }}
        .bar-label {{
            width: 80px;
            font-weight: 600;
            margin-right: 10px;
            flex-shrink: 0;
        }}
        .bar-container {{
            flex: 1;
            background-color: #e9ecef;
            border-radius: 4px;
            height: 25px;
            position: relative;
        }}
        .bar-fill {{
            background: linear-gradient(90deg, #3498db, #2ecc71);
            height: 100%;
            border-radius: 4px;
            display: flex;
            align-items: center;
            padding: 0 10px;
            color: white;
            font-weight: 600;
            font-size: 12px;
            min-width: 0;
            box-sizing: border-box;
        }}
        .timestamp {{
            color: #7f8c8d;
            font-size: 0.9em;
        }}
        .footer {{
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ecf0f1;
            color: #7f8c8d;
        }}
        .no-versions {{
            color: #e74c3c;
            font-style: italic;
        }}
        .risk-warning {{
            background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .risk-high {{
            background-color: #ffebee;
            border-left: 4px solid #e74c3c;
        }}
        .risk-medium {{
            background-color: #fff3e0;
            border-left: 4px solid #ff9800;
        }}
        .risk-low {{
            background-color: #f3e5f5;
            border-left: 4px solid #9c27b0;
        }}
        .risk-none {{
            background-color: #e8f5e8;
            border-left: 4px solid #4caf50;
        }}
        .version-type-open {{
            background-color: #ffebee;
            color: #d32f2f;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.8em;
            font-weight: bold;
        }}
        .version-type-explicit {{
            background-color: #e8f5e8;
            color: #388e3c;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.8em;
            font-weight: bold;
        }}
        .version-type-ranged {{
            background-color: #e3f2fd;
            color: #1976d2;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.8em;
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 Certified Operators Analysis Report</h1>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number">{total_operators}</div>
                <div class="stat-label">Total Operators</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{operators_with_versions}</div>
                <div class="stat-label">With Versions</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{total_versions:,}</div>
                <div class="stat-label">Total Versions</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{fbc_operators}</div>
                <div class="stat-label">FBC Operators</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{len(version_counts)}</div>
                <div class="stat-label">OpenShift Versions</div>
            </div>
        </div>


        <h3>📋 Version Type Distribution</h3>
        <div class="chart-container">
            <p>Analysis of how operators specify OpenShift version support:</p>"""

    # Add version type chart
    if version_type_counts:
        max_type_count = max(version_type_counts.values()) if version_type_counts else 1
        for version_type, count in sorted(version_type_counts.items(), key=lambda x: x[1], reverse=True):
            bar_width = (count / max_type_count) * 100
            type_colors = {
                'open_ended': 'linear-gradient(90deg, #e74c3c, #c0392b)',
                'explicit': 'linear-gradient(90deg, #27ae60, #229954)', 
                'ranged': 'linear-gradient(90deg, #3498db, #2980b9)',
                'mixed': 'linear-gradient(90deg, #f39c12, #e67e22)',
                'none': 'linear-gradient(90deg, #95a5a6, #7f8c8d)'
            }
            color = type_colors.get(version_type, 'linear-gradient(90deg, #3498db, #2ecc71)')
            type_name = version_type.replace('_', ' ').title()
            html += f"""
            <div class="bar">
                <div class="bar-label" style="width: 100px;">{type_name}</div>
                <div class="bar-container">
                    <div class="bar-fill" style="width: {bar_width}%; background: {color};">
                        {count} operators
                    </div>
                </div>
            </div>
"""

    html += """
        </div>

        <table>
            <thead>
                <tr>
                    <th>Version Type</th>
                    <th>Description</th>
                    <th>Operators</th>
                </tr>
            </thead>
            <tbody>"""
    
    # Add version type table rows dynamically
    html += f"""
                <tr>
                    <td><span class="version-type-open">Open Ended</span></td>
                    <td>Versions like "v4.8" - claim support for all subsequent versions</td>
                    <td>{version_type_counts.get('open_ended', 0)}</td>
                </tr>
                <tr>
                    <td><span class="version-type-explicit">Explicit</span></td>
                    <td>Versions like "=v4.8" - support only specific versions</td>
                    <td>{version_type_counts.get('explicit', 0)}</td>
                </tr>
                <tr>
                    <td><span class="version-type-ranged">Ranged</span></td>
                    <td>Versions like "v4.8-v4.12" - support explicit range</td>
                    <td>{version_type_counts.get('ranged', 0)}</td>
                </tr>
                <tr>
                    <td><span class="version-type-open">Mixed</span></td>
                    <td>Combination of different version types</td>
                    <td>{version_type_counts.get('mixed', 0)}</td>
                </tr>
            </tbody>
        </table>"""


    html += """

        <h2>📊 OpenShift Version Support</h2>
        <div class="chart-container">
            <h3>Top 10 OpenShift Versions by Operator Count</h3>
"""

    # Add OpenShift version chart
    for version, count in sorted_versions[:10]:
        percentage = (count / total_operators) * 100
        bar_width = (count / sorted_versions[0][1]) * 100
        html += f"""
            <div class="bar">
                <div class="bar-label">{version}</div>
                <div class="bar-container">
                    <div class="bar-fill" style="width: {bar_width}%;">
                        {count} operators ({percentage:.1f}%)
                    </div>
                </div>
            </div>
"""

    html += """
        </div>

        <h2>📦 File-Based Catalogs (FBC) Analysis</h2>
        <div class="chart-container">
            <h3>FBC Operators by OpenShift Version</h3>
"""

    # Add FBC chart
    if fbc_version_counts:
        sorted_fbc_versions = sorted(fbc_version_counts.items(), key=lambda x: x[1], reverse=True)
        max_fbc_count = max(fbc_version_counts.values()) if fbc_version_counts else 1
        
        for version, count in sorted_fbc_versions[:10]:
            bar_width = (count / max_fbc_count) * 100
            html += f"""
            <div class="bar">
                <div class="bar-label">{version}</div>
                <div class="bar-container">
                    <div class="bar-fill" style="width: {bar_width}%; background: linear-gradient(90deg, #9b59b6, #8e44ad);">
                        {count} FBC operators
                    </div>
                </div>
            </div>
"""
    else:
        html += "<p>No FBC operators found in the analysis</p>"

    html += """
        </div>

        <table>
            <thead>
                <tr>
                    <th>FBC OpenShift Version</th>
                    <th>Operators</th>
                    <th>Percentage of FBC</th>
                </tr>
            </thead>
            <tbody>
"""

    if fbc_version_counts:
        sorted_fbc_versions = sorted(fbc_version_counts.items(), key=lambda x: x[1], reverse=True)
        for version, count in sorted_fbc_versions:
            percentage = (count / fbc_operators) * 100 if fbc_operators > 0 else 0
            html += f"""
                <tr>
                    <td><strong>{version}</strong></td>
                    <td>{count}</td>
                    <td>{percentage:.1f}%</td>
                </tr>
"""
    else:
        html += """
                <tr>
                    <td colspan="3" style="text-align: center; color: #7f8c8d;">No FBC operators found</td>
                </tr>
"""

    html += """
            </tbody>
        </table>

        <h2>🏆 Top Operators by Version Count</h2>
        <table>
            <thead>
                <tr>
                    <th>Operator Name</th>
                    <th>Version Count</th>
                    <th>OpenShift Versions</th>
                    <th>Last Updated</th>
                    <th>FBC</th>
                </tr>
            </thead>
            <tbody>
"""

    for op in top_ops:
        # Get all OpenShift versions from all operator versions
        all_openshift_versions = set()
        for version in op.get('versions', []):
            all_openshift_versions.update(version.get('openshift_versions', []))
        
        versions_str = ', '.join(sorted(list(all_openshift_versions))[:5])
        if len(all_openshift_versions) > 5:
            versions_str += f" + {len(all_openshift_versions) - 5} more"
        
        last_update = op.get('last_update', 'Unknown')
        if last_update != 'Unknown':
            last_update = datetime.fromisoformat(last_update.replace('Z', '+00:00')).strftime('%Y-%m-%d')
        
        # Check if operator has FBC
        has_fbc = op.get('fbc') is not None
        fbc_indicator = "✅" if has_fbc else "❌"
        
        html += f"""
                <tr>
                    <td><strong>{op['name']}</strong></td>
                    <td>{len(op.get('versions', []))}</td>
                    <td>{versions_str if versions_str else '<span class="no-versions">No versions</span>'}</td>
                    <td class="timestamp">{last_update}</td>
                    <td style="text-align: center;">{fbc_indicator}</td>
                </tr>
"""

    html += """
            </tbody>
        </table>

        <h2>⏰ Recently Updated Operators</h2>
        <table>
            <thead>
                <tr>
                    <th>Operator Name</th>
                    <th>Last Updated</th>
                    <th>Version Count</th>
                    <th>OpenShift Versions</th>
                    <th>FBC</th>
                </tr>
            </thead>
            <tbody>
"""

    for op in recent_ops:
        last_update = datetime.fromisoformat(op['last_update'].replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M')
        
        # Get all OpenShift versions from all operator versions
        all_openshift_versions = set()
        for version in op.get('versions', []):
            all_openshift_versions.update(version.get('openshift_versions', []))
        
        versions_str = ', '.join(sorted(list(all_openshift_versions))[:3])
        if len(all_openshift_versions) > 3:
            versions_str += f" + {len(all_openshift_versions) - 3} more"
        
        # Check if operator has FBC
        has_fbc = op.get('fbc') is not None
        fbc_indicator = "✅" if has_fbc else "❌"
        
        html += f"""
                <tr>
                    <td><strong>{op['name']}</strong></td>
                    <td class="timestamp">{last_update}</td>
                    <td>{len(op.get('versions', []))}</td>
                    <td>{versions_str if versions_str else '<span class="no-versions">No versions</span>'}</td>
                    <td style="text-align: center;">{fbc_indicator}</td>
                </tr>
"""

    html += """
            </tbody>
        </table>

        <h2>🏢 Top Vendors</h2>
        <table>
            <thead>
                <tr>
                    <th>Vendor Prefix</th>
                    <th>Operator Count</th>
                    <th>Percentage</th>
                </tr>
            </thead>
            <tbody>
"""

    for vendor, count in top_vendors:
        percentage = (count / total_operators) * 100
        html += f"""
                <tr>
                    <td><strong>{vendor}</strong></td>
                    <td>{count}</td>
                    <td>{percentage:.1f}%</td>
                </tr>
"""

    html += """
            </tbody>
        </table>

        <h2>🔥 Vendor Freshness Analysis</h2>
        <p>Analysis of which vendors are actively maintaining their operators (last 6 months)</p>
        
        <div class="chart-container">
            <h3>Vendor Freshness Score (% operators updated in last 6 months)</h3>
"""

    # Add vendor freshness chart
    if fresh_vendors:
        max_score = max(stats['freshness_score'] for _, stats in fresh_vendors)
        for vendor, stats in fresh_vendors:
            bar_width = (stats['freshness_score'] / max_score) * 100 if max_score > 0 else 0
            html += f"""
            <div class="bar">
                <div class="bar-label">{vendor}</div>
                <div class="bar-container">
                    <div class="bar-fill" style="width: {bar_width}%; background: {'linear-gradient(90deg, #e74c3c, #c0392b)' if vendor == 'stackable' else 'linear-gradient(90deg, #3498db, #2ecc71)'};">
                        {stats['freshness_score']:.1f}% ({stats['recent_updates']}/{stats['count']})
                    </div>
                </div>
            </div>
"""

    html += """
        </div>

        <table>
            <thead>
                <tr>
                    <th>Vendor</th>
                    <th>Total Operators</th>
                    <th>Recent Updates</th>
                    <th>Freshness Score</th>
                    <th>Avg Days Old</th>
                </tr>
            </thead>
            <tbody>
"""

    for vendor, stats in fresh_vendors:
        highlight_class = 'style="background-color: #fff3cd;"' if vendor == 'stackable' else ''
        html += f"""
                <tr {highlight_class}>
                    <td><strong>{vendor}{'  🎯' if vendor == 'stackable' else ''}</strong></td>
                    <td>{stats['count']}</td>
                    <td>{stats['recent_updates']}</td>
                    <td>{stats['freshness_score']:.1f}%</td>
                    <td>{stats['avg_days_old']:.0f} days</td>
                </tr>
"""

    html += """
            </tbody>
        </table>

        <h2>📈 OpenShift Version Distribution</h2>
        <table>
            <thead>
                <tr>
                    <th>OpenShift Version</th>
                    <th>Operators</th>
                    <th>Percentage</th>
                </tr>
            </thead>
            <tbody>
"""

    for version, count in sorted_versions:
        percentage = (count / total_operators) * 100
        html += f"""
                <tr>
                    <td><strong>{version}</strong></td>
                    <td>{count}</td>
                    <td>{percentage:.1f}%</td>
                </tr>
"""

    html += f"""
            </tbody>
        </table>

        <h2>📅 Update Timeline</h2>
        <div class="chart-container">
            <h3>Operator Updates by Half-Year</h3>
"""

    # Add timeline chart
    if sorted_timeline:
        max_count = max(count for _, count in sorted_timeline)
        for period, count in sorted_timeline:
            bar_width = (count / max_count) * 100
            html += f"""
            <div class="bar">
                <div class="bar-label">{period}</div>
                <div class="bar-container">
                    <div class="bar-fill" style="width: {bar_width}%;">
                        {count} operators
                    </div>
                </div>
            </div>
"""
    else:
        html += "<p>No timeline data available</p>"

    html += """
        </div>

        <table>
            <thead>
                <tr>
                    <th>Period</th>
                    <th>Updates</th>
                    <th>Percentage</th>
                </tr>
            </thead>
            <tbody>
"""

    total_with_updates = sum(count for _, count in sorted_timeline)
    for period, count in sorted_timeline:
        percentage = (count / total_with_updates) * 100 if total_with_updates > 0 else 0
        html += f"""
                <tr>
                    <td><strong>{period}</strong></td>
                    <td>{count}</td>
                    <td>{percentage:.1f}%</td>
                </tr>
"""

    html += """
            </tbody>
        </table>

        <div class="footer">
"""
    
    html += f"""
            <p>Report generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>Analysis includes {operators_without_versions} operators without published versions and {fbc_operators} operators with FBC support</p>
        </div>
    </div>
</body>
</html>
"""

    return html

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 generate_html_report.py <analysis_json_file>")
        sys.exit(1)
    
    json_file = sys.argv[1]
    
    try:
        data = load_analysis_data(json_file)
        html_content = generate_html_report(data)
        
        output_file = json_file.replace('.json', '_report.html')
        with open(output_file, 'w') as f:
            f.write(html_content)
        
        print(f"HTML report generated: {output_file}")
        
    except Exception as e:
        print(f"Error generating HTML report: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()