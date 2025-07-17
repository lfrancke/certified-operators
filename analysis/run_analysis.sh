#!/bin/bash

# Certified Operators Analysis Runner
# This script mimics what the GitHub Action does

set -e

echo "🔍 Starting Certified Operators Analysis..."

# Check if required files exist
if [ ! -f "analyze_operators.py" ]; then
    echo "❌ Error: analyze_operators.py not found"
    exit 1
fi

if [ ! -f "generate_html_report.py" ]; then
    echo "❌ Error: generate_html_report.py not found"
    exit 1
fi

# Run the analysis
echo "📊 Running operator analysis..."
python3 analyze_operators.py --format json --output operator_analysis.json
python3 analyze_operators.py --format csv --output operator_analysis.csv

echo "🌐 Generating HTML report..."
python3 generate_html_report.py operator_analysis.json

# Create docs structure
echo "📁 Creating GitHub Pages structure..."
mkdir -p docs

# Copy files
cp operator_analysis_report.html docs/index.html
cp operator_analysis.json docs/
cp operator_analysis.csv docs/

# Create data download page
cat > docs/data.html << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <title>Certified Operators Analysis - Data Downloads</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            margin: 40px auto; 
            max-width: 800px; 
            line-height: 1.6;
            color: #333;
        }
        .header {
            text-align: center;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 2px solid #eee;
        }
        .download-section {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }
        .download-card {
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 20px;
            text-align: center;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .download-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        .download-link { 
            display: inline-block; 
            margin: 10px 0; 
            padding: 12px 24px; 
            background: #007acc; 
            color: white; 
            text-decoration: none; 
            border-radius: 5px; 
            font-weight: 600;
        }
        .download-link:hover { 
            background: #005a9e; 
        }
        .file-description { 
            color: #666; 
            font-size: 0.9em; 
            margin-top: 8px;
        }
        .stats {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }
        .back-link {
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #eee;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 Certified Operators Analysis</h1>
        <p>Download the latest analysis data and reports</p>
    </div>
    
    <div class="download-section">
        <div class="download-card">
            <h3>📄 JSON Data</h3>
            <p>Complete analysis data with full operator details, versions, and metadata.</p>
            <a href="operator_analysis.json" class="download-link" download>Download JSON</a>
            <div class="file-description">Perfect for API consumption and custom analysis</div>
        </div>
        
        <div class="download-card">
            <h3>📊 CSV Data</h3>
            <p>Tabular data format compatible with Excel, Google Sheets, and data analysis tools.</p>
            <a href="operator_analysis.csv" class="download-link" download>Download CSV</a>
            <div class="file-description">Ideal for spreadsheet analysis and pivoting</div>
        </div>
        
        <div class="download-card">
            <h3>🌐 Interactive Report</h3>
            <p>Full HTML dashboard with charts, vendor analysis, and timeline insights.</p>
            <a href="index.html" class="download-link">View Dashboard</a>
            <div class="file-description">Complete visual analysis with interactive elements</div>
        </div>
    </div>
    
    <div class="stats">
        <h3>📈 Latest Analysis Includes:</h3>
        <ul>
            <li>477+ certified operators analyzed</li>
            <li>3,700+ operator versions tracked</li>
            <li>Git history analysis for freshness metrics</li>
            <li>OpenShift version compatibility mapping</li>
            <li>FBC (File-Based Catalog) support detection</li>
            <li>Vendor activity and maintenance patterns</li>
        </ul>
    </div>
    
    <div class="back-link">
        <a href="https://github.com/redhat-openshift-ecosystem/certified-operators">← Back to Repository</a>
    </div>
    
    <script>
        // Add timestamp
        document.addEventListener('DOMContentLoaded', function() {
            const timestamp = new Date().toISOString();
            document.body.appendChild(Object.assign(document.createElement('p'), {
                innerHTML: '<strong>Generated:</strong> ' + timestamp,
                style: 'text-align: center; color: #666; font-size: 0.9em; margin-top: 20px;'
            }));
        });
    </script>
</body>
</html>
EOF

# Add navigation to main report
if grep -q "Download Data Files" docs/index.html; then
    echo "✅ Navigation link already exists"
else
    sed -i 's/<h1>🚀 Certified Operators Analysis Report<\/h1>/<h1>🚀 Certified Operators Analysis Report<\/h1>\n        <p style="text-align: center; margin: 20px 0;"><a href="data.html" style="color: #3498db; text-decoration: none; font-weight: 600;">📥 Download Data Files<\/a><\/p>/' docs/index.html
fi

echo "✅ Analysis complete!"
echo ""
echo "📁 Generated files:"
echo "  - operator_analysis.json ($(du -h operator_analysis.json | cut -f1))"
echo "  - operator_analysis.csv ($(du -h operator_analysis.csv | cut -f1))"
echo "  - docs/index.html (Interactive dashboard)"
echo "  - docs/data.html (Download page)"
echo ""
echo "🌐 To test locally:"
echo "  cd docs && python3 -m http.server 8000"
echo "  Then visit: http://localhost:8000"
echo ""
echo "🚀 Ready for GitHub Pages deployment!"