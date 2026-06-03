@echo off
REM CareConnect Streamlit App Launcher for Windows

echo 🏥 Starting CareConnect AI Patient Follow-Up System...
echo.

REM Check if virtual environment exists
if not exist "venv\" (
    echo ❌ Virtual environment not found. Please run:
    echo    python -m venv venv
    echo    venv\Scripts\activate
    echo    pip install -r requirements.txt
    exit /b 1
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Check if .env exists
if not exist ".env" (
    echo ⚠️  .env file not found. Creating from template...
    copy .env.template .env
    echo ✅ Please edit .env and add your OPENAI_API_KEY
    exit /b 1
)

REM Check if ChromaDB exists
if not exist "chroma_db\" (
    echo ⚠️  ChromaDB not initialized. Building RAG vector store...
    cd src
    python main.py --rebuild-rag
    cd ..
)

REM Start Streamlit
echo ✅ Launching Streamlit dashboard...
cd src
streamlit run frontend/app.py

