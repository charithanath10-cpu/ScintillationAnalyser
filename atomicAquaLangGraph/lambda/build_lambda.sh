#!/bin/bash
# build_lambda.sh — packages novatel_processor.py + src/ into lambda_package.zip
# Run from the atomicAquaLangGraph/ directory:
#   cd atomicAquaLangGraph
#   bash lambda/build_lambda.sh

set -e
echo "Building Lambda package..."

STAGING="lambda/_staging"
ZIP="lambda/lambda_package.zip"

# Clean
rm -rf "$STAGING" "$ZIP"
mkdir -p "$STAGING"

# Copy handler + src
cp lambda/novatel_processor.py "$STAGING/"
rsync -a --exclude='__pycache__' --exclude='*.pyc' --exclude='*.egg-info' \
    src/ "$STAGING/src/"

# Install dependencies into staging
echo "Installing dependencies..."
pip install \
    boto3 \
    "langchain==1.3.10" \
    "langchain-core==1.4.8" \
    "langchain-aws==1.6.0" \
    "langgraph==1.2.6" \
    "langgraph-prebuilt==1.1.0" \
    "pandas==3.0.3" \
    "numpy==2.4.6" \
    "bedrock-agentcore==1.15.0" \
    "beautifulsoup4==4.15.0" \
    "lxml==6.1.1" \
    "python-dotenv==1.2.2" \
    "tiktoken==0.13.0" \
    -t "$STAGING" \
    --quiet

# Zip
echo "Zipping..."
cd "$STAGING"
zip -r "../../$ZIP" . -q
cd ../..

# Cleanup
rm -rf "$STAGING"

echo ""
echo "Done! $ZIP is ready to upload to AWS Lambda."
echo ""
echo "Next steps:"
echo "  1. Go to AWS Lambda console → Create function"
echo "  2. Name: novatel_processor, Runtime: Python 3.11"
echo "  3. Memory: 3008 MB, Timeout: 900 seconds"
echo "  4. Upload $ZIP as the deployment package"
echo "  5. Set Handler: novatel_processor.handler"
echo "  6. Environment variables:"
echo "       S3_BUCKET      = your-bucket-name"
echo "       AWS_REGION     = ap-south-1"
echo "       BEDROCK_MODEL_ID = us.anthropic.claude-sonnet-4-6"
echo "       KB_ID          = FH00WKSBPL"
echo "  7. IAM role needs: s3:GetObject, s3:PutObject, s3:DeleteObject, bedrock:InvokeModel"
