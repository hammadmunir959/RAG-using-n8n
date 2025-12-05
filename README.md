# Document Intelligence WebApp

A modern web application that allows users to upload documents (PDF, CSV, JSON) and chat with an AI assistant that answers questions based on the uploaded documents. Built with React frontend, FastAPI backend, and n8n workflows for document processing and AI intelligence.

## 🎯 Features

- **Document Upload**: Drag-and-drop interface for uploading PDF, CSV, and JSON files
- **AI Chat Interface**: Natural language Q&A about uploaded documents
- **Vector Store**: Documents are automatically processed, embedded, and stored
- **Modern UI**: Beautiful, responsive interface with smooth animations

## 🏗️ Architecture

```
Frontend (React) → Backend (FastAPI) → n8n Workflows → AI Models (Groq + HuggingFace)
```

- **Frontend**: React + Vite for the user interface
- **Backend**: FastAPI as a proxy layer to n8n webhooks
- **n8n**: Handles document processing, embeddings, vector storage, and AI responses

## 📋 Prerequisites

- Docker and Docker Compose (for n8n)
- Python 3.9+ (for backend)
- Node.js 18+ and npm (for frontend)
- n8n running on localhost:5678 (via Docker)

## 🚀 Quick Start

### Option 0: Docker (Production-Ready)

Build and run the entire application as a single Docker image (<100MB):

```bash
# Build the image
chmod +x build-docker.sh
./build-docker.sh your-dockerhub-username

# Or build manually
docker build -t your-username/doc-intel:latest .

# Run with docker-compose (recommended)
docker-compose -f docker-compose.prod.yml up -d

# Or run manually
docker run -d -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -e N8N_BASE_URL=http://host.docker.internal:5678 \
  -e N8N_UPLOAD_WEBHOOK_ID=d5f0f619-e0b4-4e7b-a9f4-d5b84d978651 \
  -e N8N_CHAT_WEBHOOK_ID=66219e80-fbed-4664-a11d-4a05167fbad2 \
  your-username/doc-intel:latest
```

**Push to Docker Hub:**
```bash
docker login
docker push your-username/doc-intel:latest
```

**Access the application at: http://localhost:8000**

### Option 1: One-Command Start (Recommended)

The easiest way to start all services is using the provided startup script:

```bash
chmod +x start.sh
./start.sh
```

This script will:
- ✅ Check if n8n is running, start it if needed
- ✅ Set up and start the FastAPI backend on port 8001
- ✅ Set up and start the React frontend on port 3000
- ✅ Display all service URLs

**Access your application at: http://localhost:3000**

Press `Ctrl+C` to stop all services.

### Option 2: Manual Setup

If you prefer to start services manually:

#### 1. Start n8n (if not already running)

```bash
docker compose up -d
```

Verify n8n is running at: http://localhost:5678

#### 2. Set up Backend

```bash
cd backend

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the backend server (defaults to port 8000, or set PORT env var)
PORT=8001 python main.py
```

The backend will run on http://localhost:8001

#### 3. Set up Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The frontend will run on http://localhost:3000

#### 4. Access the Application

Open your browser and navigate to: **http://localhost:3000**

## 📥 Setting up n8n Workflow

Before using the application, you need to import the workflow into n8n:

1. **Start n8n** (if not already running):
   ```bash
   docker compose up -d
   ```

2. **Access n8n**: Open http://localhost:5678 in your browser
   - Default credentials: `admin` / `admin`

3. **Import the workflow**:
   - Click "Workflows" in the sidebar
   - Click "Import from File" or use the "+" button
   - Select `workflow.json` from the project root
   - The workflow will be imported with all nodes configured

4. **Configure API credentials** (if needed):
   - The workflow uses Groq and HuggingFace APIs
   - Click on the "Groq Chat Model" node and add your Groq API key
   - Click on the "HuggingFace Embeddings" nodes and add your HuggingFace API key
   - You can get API keys from:
     - Groq: https://console.groq.com/
     - HuggingFace: https://huggingface.co/settings/tokens

5. **Activate the workflow**:
   - Click the toggle switch in the top-right corner to activate the workflow
   - Both workflows (upload and chat) should be active

6. **Verify webhook URLs**:
   - The webhook IDs in the workflow should match the ones in `backend/main.py`
   - Default IDs are already configured correctly

## 🔧 Configuration

### Backend Environment Variables

Create a `.env` file in the `backend` directory (optional, defaults are set):

```env
N8N_BASE_URL=http://localhost:5678
N8N_UPLOAD_WEBHOOK_ID=d5f0f619-e0b4-4e7b-a9f4-d5b84d978651
N8N_CHAT_WEBHOOK_ID=66219e80-fbed-4664-a11d-4a05167fbad2
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=admin
PORT=8001
```

**Note**: 
- The backend runs on port 8001 by default to avoid conflicts with other services. You can change this by setting the `PORT` environment variable.
- If your n8n instance has basic auth enabled (which it does by default in the docker-compose.yml), make sure the credentials match.

**Note**: 
- Make sure these webhook IDs match your actual n8n workflow webhook IDs. You can find them in your n8n workflow editor.
- The default webhook IDs match the workflow.json file included in this repository.
- To use a different workflow, import `workflow.json` into n8n or update the webhook IDs accordingly.

## 📁 Project Structure

```
n8n1/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── requirements.txt     # Python dependencies
│   └── venv/               # Python virtual environment (created on first run)
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── UploadPage.jsx    # Document upload component
│   │   │   ├── UploadPage.css
│   │   │   ├── ChatPage.jsx      # Chat interface component
│   │   │   ├── ChatPage.css
│   │   │   ├── Sidebar.jsx       # Navigation sidebar
│   │   │   └── Sidebar.css
│   │   ├── App.jsx          # Main app component
│   │   ├── App.css
│   │   ├── main.jsx         # React entry point
│   │   └── index.css        # Global styles
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── dist/                # Production build output
├── docker-compose.yml       # n8n Docker configuration
├── workflow.json            # n8n workflow configuration
├── start.sh                 # Quick start script
└── README.md
```

## 🔌 API Endpoints

### POST /api/upload

Upload a document to the knowledge base.

**Request:**
- Content-Type: `multipart/form-data`
- Body: `file` (PDF, CSV, or JSON)

**Response:**
```json
{
  "success": true,
  "message": "Document 'example.pdf' uploaded and processed successfully",
  "filename": "example.pdf"
}
```

### POST /api/chat

Send a chat message and get AI response.

**Request:**
```json
{
  "message": "What is in the document?"
}
```

**Response:**
```json
{
  "success": true,
  "response": "Based on the document, ..."
}
```

## 🎨 Usage

1. **Upload Documents**:
   - Navigate to the "Upload Documents" page
   - Drag and drop files or click "Browse Files"
   - Supported formats: PDF, CSV, JSON
   - Click "Upload Document" to process

2. **Chat with Documents**:
   - Navigate to the "Chat with Documents" page
   - Type your question in the input field
   - The AI will search through uploaded documents and provide answers
   - View conversation history in the chat window

## 🛠️ Development

### Backend Development

```bash
cd backend
python main.py
```

The server will reload automatically on code changes.

### Frontend Development

```bash
cd frontend
npm run dev
```

Hot module replacement is enabled for instant updates.

### Building for Production

**Frontend:**
```bash
cd frontend
npm run build
```

The built files will be in `frontend/dist/`

**Backend:**
The FastAPI app can be deployed using uvicorn or any ASGI server:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

## 🔒 Security Notes

- The backend acts as a proxy to protect n8n webhooks from direct exposure
- CORS is configured to allow requests from the frontend only
- For production, consider:
  - Adding authentication/authorization
  - Using environment variables for sensitive data
  - Implementing rate limiting
  - Using HTTPS

## 🐛 Troubleshooting

### n8n webhook not found
- Verify n8n is running: `docker ps | grep n8n`
- Check webhook IDs in n8n workflow editor
- Ensure workflows are activated in n8n

### CORS errors
- Verify backend CORS settings allow your frontend origin
- Check that backend is running on port 8001
- If you see 405 Method Not Allowed, restart the backend server to apply CORS fixes

### File upload fails (500 error)
- **Backend not running**: Make sure the backend is running on port 8001
  ```bash
  cd backend
  source venv/bin/activate
  python main.py
  ```
- **n8n not running**: Verify n8n is running: `docker ps | grep n8n`
- **Webhook not active**: Check in n8n that the workflow is activated
- **Webhook ID mismatch**: Verify webhook IDs in n8n match the ones in backend code
- **Check backend logs**: Look for error messages in the backend console
- Check file size limits
- Verify file type is supported (PDF, CSV, JSON)
- Check n8n workflow is active and webhook is public

## 📝 License

This project is open source and available for personal and commercial use.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

**Built with ❤️ using React, FastAPI, and n8n**

