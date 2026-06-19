@echo off
echo ========================================
echo Restarting NovAtel AI Assistant
echo ========================================
echo.

echo Step 1: Stopping any running Streamlit processes...
taskkill /F /IM streamlit.exe 2>nul
timeout /t 2 /nobreak >nul

echo Step 2: Activating virtual environment...
call .venv\Scripts\activate.bat

echo Step 3: Starting Streamlit app...
echo.
echo The app will open at http://localhost:8501
echo Press Ctrl+C to stop the server
echo.

python -m streamlit run streamlit_app.py

pause
