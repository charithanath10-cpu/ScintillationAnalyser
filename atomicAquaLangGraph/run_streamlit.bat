@echo off
echo Starting NovAtel AI Assistant Streamlit App...
echo.

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Check if .env file exists
if not exist .env (
    echo WARNING: .env file not found!
    echo Please create a .env file with your AWS configuration.
    echo See STREAMLIT_SETUP.md for details.
    echo.
    pause
    exit /b 1
)

REM Start Streamlit
echo Starting Streamlit server...
echo The app will open in your browser at http://localhost:8501
echo Press Ctrl+C to stop the server
echo.

python -m streamlit run streamlit_app.py

pause
