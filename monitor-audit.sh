#!/bin/bash
# Monitor FinOps Audit Performance
# Usage: ./monitor-audit.sh

echo "🔍 Monitoring FinOps Audit Performance..."
echo "================================================"
echo ""
echo "Watching for:"
echo "  ✓ Smart region filtering"
echo "  ✓ Parallel worker count (15 workers)"
echo "  ✓ Global service scanning"
echo "  ✓ Audit completion time"
echo ""
echo "Press Ctrl+C to stop monitoring"
echo "================================================"
echo ""

docker logs aws-cost-backend -f 2>&1 | grep --line-buffered -E "(Smart filtering|Filtered.*regions|regions in parallel|Scanning CloudFront|Scanning Route53|Starting audit|Audit completed|Error)"
