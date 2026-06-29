@echo off
REM build_lambda.bat — Build Lambda package using Docker (Windows)
REM Requires Docker Desktop with WSL2 backend running

setlocal
cd /d "%~dp0"

echo === Cleaning previous build ===
if exist _build rmdir /s /q _build
if exist lambda_package.zip del lambda_package.zip
mkdir _build

echo === Installing dependencies for Amazon Linux 2023 / Python 3.11 ===
docker run --rm ^
  -v "%cd%\_build":/out ^
  -v "%cd%\requirements_lambda.txt":/requirements.txt ^
  public.ecr.aws/lambda/python:3.11 ^
  pip install -r /requirements.txt -t /out --no-cache-dir

if errorlevel 1 (
    echo ERROR: Docker build failed. Is Docker Desktop running?
    exit /b 1
)

echo === Copying handler and src/ ===
copy novatel_processor.py _build\
xcopy /E /I /Q ..\src _build\src

echo === Creating lambda_package.zip ===
cd _build
powershell -Command "Compress-Archive -Path * -DestinationPath ..\lambda_package.zip -Force"
cd ..

echo === Done: lambda_package.zip ===
echo.
echo Upload to Lambda:
echo   aws lambda update-function-code --function-name novatel_processor --zip-file fileb://lambda_package.zip --region ap-south-1

endlocal
