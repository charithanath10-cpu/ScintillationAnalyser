#!/bin/bash
# build_lambda.sh — Build Lambda deployment package with Linux-native binaries
# Requires Docker Desktop running on Windows (WSL2 backend)
#
# Usage:  bash build_lambda.sh
# Output: lambda_package.zip  (upload this to the Lambda function)

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Cleaning previous build ==="
rm -rf _build lambda_package.zip
mkdir -p _build

echo "=== Installing dependencies for Amazon Linux 2023 / Python 3.11 ==="
docker run --rm \
  -v "$SCRIPT_DIR/_build":/out \
  -v "$SCRIPT_DIR/requirements_lambda.txt":/requirements.txt \
  public.ecr.aws/lambda/python:3.11 \
  pip install -r /requirements.txt -t /out --no-cache-dir

echo "=== Copying handler and src/ ==="
cp novatel_processor.py _build/
cp -r ../src _build/src

echo "=== Removing unnecessary files to reduce zip size ==="
find _build -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find _build -name "*.pyc" -delete 2>/dev/null || true
find _build -name "*.pyo" -delete 2>/dev/null || true
find _build -name "tests" -type d -exec rm -rf {} + 2>/dev/null || true
find _build -name "test_*.py" -delete 2>/dev/null || true
find _build -name "*.dist-info" -type d -exec rm -rf {} + 2>/dev/null || true

echo "=== Creating lambda_package.zip ==="
cd _build
zip -r ../lambda_package.zip . -q
cd ..

SIZE=$(du -sh lambda_package.zip | cut -f1)
echo "=== Done: lambda_package.zip ($SIZE) ==="
echo ""
echo "Upload to Lambda:"
echo "  aws lambda update-function-code \\"
echo "    --function-name novatel_processor \\"
echo "    --zip-file fileb://lambda_package.zip \\"
echo "    --region ap-south-1"
