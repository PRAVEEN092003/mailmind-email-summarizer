# MailMind — Intelligent Email Thread Summarizer

MailMind is a local AI-powered email summarization application that
extracts important information from email conversations.

## Features

- AI-powered email summarization
- Action item and deadline extraction
- Responsible person identification
- Email file (.eml) upload and parsing
- Summary history
- User authentication
- SQLite database storage
- Local AI inference using Ollama

## Technologies Used

- Frontend: React, Vite
- Backend: Python, FastAPI
- AI: Ollama, Qwen 2.5 3B
- Database: SQLite

## System Requirements

- Windows 10 or Windows 11
- Python 3.12
- Node.js and npm
- Ollama
- Internet connection for initial software and model downloads

## Installation and Setup

### Step 1: Extract the Project

1. Copy the MailMind ZIP file to your computer.
2. Right-click the ZIP file.
3. Select Extract All.
4. Open the extracted project folder.

### Step 2: Install Python

Install Python 3.12 if it is not already installed.

Verify the installation:

    python --version

### Step 3: Install Node.js

Install Node.js LTS.

Verify the installation:

    node --version
    npm --version

### Step 4: Install Ollama

Install Ollama for Windows.

After installation, open Command Prompt and download the model:

    ollama pull qwen2.5:3b

Wait until the model download completes.

Verify the model:

    ollama list

### Step 5: Configure the Backend

Open Command Prompt.

Navigate to the backend directory:

    cd /d "C:\path\to\MailMind\backend"

Create a Python virtual environment:

    python -m venv venv

Activate the environment:

    venv\Scripts\activate.bat

Install the dependencies:

    python -m pip install -r requirements.txt

If the project includes `.env.example`, create a copy named `.env`.

Configure the environment variables according to the existing project
configuration. Do not share production secrets or passwords.

### Step 6: Start the Backend

From the backend directory, run:

    python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

Keep this Command Prompt window open.

Verify the backend:

    http://127.0.0.1:8000/api/health

API documentation:

    http://127.0.0.1:8000/docs

### Step 7: Install Frontend Dependencies

Open another Command Prompt window.

Navigate to the frontend directory:

    cd /d "C:\path\to\MailMind\frontend"

Install dependencies:

    npm install

### Step 8: Start the Frontend

Run:

    npm run dev

Open the local URL displayed in the terminal.

Usually:

    http://localhost:5173

Keep both the backend and frontend running while using the application.

## How to Use

1. Open MailMind in your browser.
2. Register an account or log in.
3. Open the Summarize page.
4. Paste an email conversation or upload an .eml file.
5. Click Summarize.
6. Review the generated summary, action items, deadlines,
   responsible persons, and urgency.
7. Access previously saved summaries through History.

## Database

MailMind uses SQLite for persistent storage.

The database file is:

    backend/email_summarizer.db

Keep a backup of the database if you need to preserve existing users
and summary history.

Do not delete or replace an existing database without backing it up.

## Troubleshooting

### Ollama is not connected

Ensure Ollama is running and the required model is installed:

    ollama list

### Backend dependency errors

Activate the virtual environment and run:

    python -m pip install -r requirements.txt

### Frontend dependency errors

From the frontend directory, run:

    npm install

### Port already in use

Stop the application using the occupied port or configure an available
port and update the frontend API configuration if necessary.

### Database errors

Check that the backend has permission to access its database directory
and that the database file exists when required.

## Important Notes

- Ollama and the required model must be installed on each new computer.
- Python and Node.js dependencies must be installed on each new computer.
- The application runs locally; AI inference uses the configured local
  Ollama model.
- Keep environment secrets private.
- Back up the SQLite database before making changes.

## License

Specify the project license here if applicable.