#!/bin/bash
# CareConnect Streamlit App Launcher

echo "🏥 Starting CareConnect AI Patient Follow-Up System..."
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run:"
    echo "   python3 -m venv venv"
    echo "   source venv/bin/activate"
    echo "   pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Creating from template..."
    cp .env.template .env
    echo "✅ Please edit .env and add your OPENAI_API_KEY"
    exit 1
fi

# Check if ChromaDB exists
if [ ! -d "chroma_db" ]; then
    echo "⚠️  ChromaDB not initialized. Building RAG vector store..."
    cd src
    python main.py --rebuild-rag
    cd ..
fi

# Start Streamlit
echo "✅ Launching Streamlit dashboard..."
cd src
streamlit run frontend/app.py

#  
