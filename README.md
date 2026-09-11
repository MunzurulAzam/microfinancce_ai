# Microfinance AI Analysis API

A Flask-based REST API that provides microfinance client and group analysis with AI-powered insights.

## 🚀 Features

- **CSV Data Upload**: Upload your microfinance dataset
- **Client Analysis**: Analyze individual client performance
- **Group Analysis**: View collective group performance
- **Conversational AI**: Ask natural language questions via `/api/ask`
- **AI-Powered Insights**: Smart recommendations using Ollama Cloud
- **Risk Assessment**: Identify high-risk clients and groups
- **Performance Metrics**: Business sector analysis and top performers

## 📋 Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Virtual environment (recommended)

## 🛠️ Installation

### 1. Create Virtual Environment

```bash
cd /Users/smini/Downloads/flutterWorkStation/ai
python3 -m venv env
source env/bin/activate  # Mac/Linux
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Ollama Cloud

Copy `.env.example` to `.env`, fill warehouse credentials and `OLLAMA_API_KEY`.
All inference uses the cloud directly; no local model download is required.

## 🏃 Run the Application

```bash
python app.py
```

The API will be available at: `http://localhost:5001`

## 📡 API Endpoints

### 💡 Conversational AI (Recommended)

#### Ask Anything
```bash
POST /api/ask
Content-Type: application/json

{
  "question": "Analyze client John Doe"
}
```

### Data Management

#### Upload CSV Data
```bash
POST /api/upload
Content-Type: multipart/form-data

# Example with curl:
curl -X POST http://localhost:5001/api/upload \
  -F "file=@data/master_data.csv"
```

#### Get Statistics
```bash
GET /api/stats
```

#### List Clients
```bash
GET /api/clients?limit=10&offset=0&search=John
```

#### List Groups
```bash
GET /api/groups?limit=10&offset=0&search=Group
```

### Analysis

#### Analyze Client
```bash
POST /api/analyze/client
{ "client_name": "John Doe" }
```

#### Analyze Group
```bash
POST /api/analyze/group
{ "group_name": "Group A" }
```

#### Get Quick Insights
```bash
GET /api/analyze/insights
```

#### Get Top Clients/Groups
```bash
GET /api/analyze/top-clients?limit=10
GET /api/analyze/top-groups?limit=10
```

#### Risk Analysis
```bash
GET /api/analyze/risk-analysis?threshold=3
```

## 📁 Project Structure

```
ai/
├── app.py                      # Main Flask application
├── config.py                   # Configuration settings
├── requirements.txt            # Python dependencies
├── models/
│   └── llama_handler.py       # AI model integration
├── services/
│   ├── data_processor.py      # Data preprocessing
│   ├── analyzer.py            # Analysis functions
│   └── performance.py         # Performance calculations
├── routes/
│   ├── data.py                # Data endpoints
│   ├── analysis.py            # Analysis endpoints
│   └── ask.py                 # Conversational endpoints
└── data/
    └── uploads/               # Uploaded CSV files
```

## AI Models and Reports

- Qwen 3.5 397B: text, SQL and report evidence selection.
- MiniMax M3: document vision.
- Ask **Group Performance Report August 2026** in Ask AI for preview and PDF.
- [Report API, source definitions and .NET integration](docs/report-api.md).
- Cloud failures preserve deterministic report tables and existing scoring logic.

## ⚠️ Important Notes

1. **CORS**: Configured to allow `http://localhost:5173` (React) by default.
2. **Data**: In-memory storage. Restarting the server clears the data.
3. **Format**: Ensure your CSV has required columns like `clientName`, `loanAmount`, `OverdueCollectionCount`, etc.

## 📄 License

MIT License

### Persistent chat workspace

Ask AI and Data Q&A now share browser-local conversations with follow-ups. See [chat storage, context API and .NET forwarding](docs/chat-workspace.md) for the contract, browser limitations and test commands.
