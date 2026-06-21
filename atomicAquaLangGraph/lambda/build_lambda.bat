@echo off
REM build_lambda.bat — packages novatel_processor.py + src/ into lambda_package.zip
REM Run this from the atomicAquaLangGraph/ directory:
REM   cd atomicAquaLangGraph
REM   lambda\build_lambda.bat

echo Building Lambda package...

REM Clean old zip
if exist lambda\lambda_package.zip del lambda\lambda_package.zip

REM Create a temp staging folder
if exist lambda\_staging rmdir /s /q lambda\_staging
mkdir lambda\_staging

REM Copy the handler
copy lambda\novatel_processor.py lambda\_staging\novatel_processor.py

REM Copy the src folder (minus __pycache__ and .egg-info)
xcopy src lambda\_staging\src /E /I /Q /EXCLUDE:lambda\xcopy_exclude.txt

REM Create the exclude list
echo __pycache__> lambda\xcopy_exclude.txt
echo .egg-info>> lambda\xcopy_exclude.txt
echo .pyc>> lambda\xcopy_exclude.txt

REM Install dependencies into the staging folder
echo Installing dependencies...
pip install ^
    boto3 ^
    langchain==1.3.10 ^
    langchain-core==1.4.8 ^
    langchain-aws==1.6.0 ^
    langgraph==1.2.6 ^
    langgraph-prebuilt==1.1.0 ^
    pandas==3.0.3 ^
    numpy==2.4.6 ^
    bedrock-agentcore==1.15.0 ^
    beautifulsoup4==4.15.0 ^
    lxml==6.1.1 ^
    python-dotenv==1.2.2 ^
    tiktoken==0.13.0 ^
    -t lambda\_staging ^
    --quiet

REM Zip everything
echo Zipping...
powershell -Command "Compress-Archive -Path 'lambda\_staging\*' -DestinationPath 'lambda\lambda_package.zip' -Force"

REM Cleanup staging
rmdir /s /q lambda\_staging

echo.
echo Done! lambda\lambda_package.zip is ready to upload to AWS Lambda.
echo.
echo Next steps:
echo   1. Go to AWS Lambda console
echo   2. Create function: novatel_processor, Runtime: Python 3.11
echo   3. Memory: 3008 MB, Timeout: 900 seconds
echo   4. Upload lambda\lambda_package.zip
echo   5. Set Handler to: novatel_processor.handler
echo   6. Add env vars: S3_BUCKET, AWS_REGION, BEDROCK_MODEL_ID, KB_ID
echo   7. Attach IAM role with S3 + Bedrock permissions
