# MailMind — Intelligent Email Thread Summarizer

MailMind is an AI-powered email summarization application designed to help users understand lengthy email conversations quickly. It extracts key information, highlights important discussions, identifies action items, and organizes deadlines into a structured summary.

The application uses a locally running AI model to process email content.

## Features

- **AI-Powered Summarization** — Convert lengthy email conversations into concise summaries.
- **Action Item Extraction** — Identify tasks mentioned in email threads.
- **Deadline Identification** — Extract deadlines and time-sensitive information.
- **Responsible Person Detection** — Identify people associated with specific tasks when stated in the email.
- **Email File Upload** — Upload `.eml` files for summarization.
- **Structured Results** — Organize summaries, decisions, discussion points, and unanswered questions.
- **Summary History** — Access previously generated summaries.
- **User Authentication** — Register and log in to access the application.
- **Local AI Processing** — Generate summaries using a locally running language model.
- **Caching** — Reuse previously generated summaries when the input matches.

## Technology Stack

| Component | Technology |
|---|---|
| Frontend | React, Vite |
| Backend | Python, FastAPI |
| AI Runtime | Ollama |
| AI Model | Qwen 2.5 3B |
| Database | SQLite |
| Authentication | JWT |
| Password Security | bcrypt |

## Architecture

```text
User
 |
 v
React Frontend
 |
 v
FastAPI Backend
 |
 +---- Email Parsing
 |
 +---- AI Summarization
 |        |
 |        v
 |      Ollama
 |        |
 |        v
 |    Qwen 2.5 3B
 |
 +---- SQLite Database
 |
 v
Structured Email Summary
```

## Prerequisites

Install the following software before running the project:

- Python 3.12
- Node.js and npm
- Git
- Ollama

A Windows computer is recommended for the setup instructions below.

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/PRAVEEN092003/mailmind-email-summarizer.git
cd mailmind-email-summarizer
```

### 2. Download the AI Model

Install Ollama, open a terminal, and run:

```bash
ollama pull qwen2.5:3b
```

Verify that the model is available:

```bash
ollama list
```

Keep Ollama running while using MailMind.

### 3. Configure the Backend

Open a terminal in the project directory.

Navigate to the backend:

```bash
cd backend
```

Create a virtual environment:

```bash
python -m venv venv
```

Activate the environment on Windows Command Prompt:

```cmd
venv\Scripts\activate.bat
```

For Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

Install the Python dependencies:

```bash
python -m pip install -r requirements.txt
```

If the project includes `.env.example`, copy it to `.env` and configure the required environment variables according to the existing configuration.

Do not commit passwords, secrets, or private environment files to GitHub.

### 4. Start the Backend

From the backend directory, run:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The backend should be available at:

```text
http://127.0.0.1:8000
```

Health check:

```text
http://127.0.0.1:8000/api/health
```

API documentation:

```text
http://127.0.0.1:8000/docs
```

Keep the backend terminal open.

### 5. Configure the Frontend

Open another terminal and navigate to the frontend directory:

```bash
cd frontend
```

Install the dependencies:

```bash
npm install
```

### 6. Start the Frontend

Run:

```bash
npm run dev
```

Open the local URL displayed in the terminal. The default Vite development URL is usually:

```text
http://localhost:5173
```

Keep both the backend and frontend running while using the application.

## How to Use

1. Open MailMind in your browser.
2. Register a new account or log in.
3. Open the summarization interface.
4. Paste an email conversation or upload an `.eml` file.
5. Start the summarization process.
6. Review the generated summary, discussion points, action items, deadlines, and unanswered questions.
7. Open the history section to access previously saved summaries.

## Database

MailMind uses SQLite to store application data and summary history.

The database is normally located at:

```text
backend/email_summarizer.db
```

The database may be initialized automatically by the application, depending on the existing backend configuration.

If you need to preserve existing users and summaries, back up the database before replacing or deleting it.

Do not upload a database containing private user information to a public repository.

## Troubleshooting

### Ollama Connection Error

Ensure Ollama is installed and running.

Check available models:

```bash
ollama list
```

If the required model is missing:

```bash
ollama pull qwen2.5:3b
```

### Backend Dependency Errors

Activate the virtual environment and reinstall the dependencies:

```bash
python -m pip install -r requirements.txt
```

### Frontend Dependency Errors

From the frontend directory, run:

```bash
npm install
```

### Port Already in Use

Stop the application occupying the required port or configure an available port and update the corresponding frontend API configuration if necessary.

### Summarization Is Slow

Processing time depends on the email length, available system resources, and local AI inference performance.

## Privacy

MailMind is designed to perform AI inference using a locally running Ollama model.

Application data is stored according to the configured backend and database implementation. Users should avoid submitting sensitive information to systems they do not control.

## Future Improvements

- Improved summary accuracy
- Better extraction of action items and deadlines
- Enhanced email thread handling
- Additional usability and accessibility improvements
- Performance optimization

## License

No license has been specified yet. All rights are reserved by default unless a license is added to this repository.

## Author

PRAVEEN R   (B.TECH CSBS)

**Praveen**

GitHub: [PRAVEEN092003](https://github.com/PRAVEEN092003)
