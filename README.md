# 🧠 Vanshika AI Persona Project
The Vanshika AI Persona project is a comprehensive application that utilizes natural language processing (NLP) and machine learning (ML) to create a conversational AI persona. The project consists of multiple components, including a retrieval-augmented generator (RAG) pipeline, a FastAPI backend, and various services for handling tasks such as query embedding, semantic retrieval, and calendar integration. The primary goal of the project is to provide a conversational AI interface that can engage in meaningful discussions and respond to user queries in a contextually relevant manner.

## 🚀 Features
- **RAG Pipeline**: A retrieval-augmented generator pipeline that enables the AI persona to retrieve and generate contextually relevant responses to user queries.
- **FastAPI Backend**: A FastAPI application that provides a RESTful API for interacting with the AI persona and handling tasks such as chat, calendar, and VAPI functionality.
- **Query Embedding**: A service that utilizes Google Gemini for embedding queries and performing cosine-similarity search via Supabase.
- **Semantic Retrieval**: A service that retrieves relevant context chunks for a given query using RAG.
- **Calendar Integration**: A service that integrates with the Cal.com API v2 for fetching available time slots, booking time slots, and fetching booking details.
- **Chat Interface**: A streaming response for chat messages with RAG-augmented context.
- **Note:** **Outbound calling** is fully integrated through Vapi. During testing, the free Vapi phone number could successfully authenticate and initiate outbound call requests. However, Vapi's free phone numbers do not support international calling, so calls to Indian numbers require either a paid Vapi number or an imported Twilio number. **The integration is complete and can be verified using supported US phone numbers.**

## RAG Pipeline

- **Embedding model:** Gemini `gemini-embedding-001` with 768 dimensions
- **Vector DB:** Supabase pgvector with HNSW index
- **Chunking:** Token-aware chunking (400 tokens, 50 token overlap) using tiktoken
- **Retrieval:** Cosine similarity search via `match_documents` SQL function
- **Sources:** Resume PDF + 21 GitHub repos (READMEs, commits, file structure)
- **Total chunks:** 137 chunks indexed
- **Similarity threshold:** 0.4
- **Top-k:** 5 chunks per query

## 🛠️ Tech Stack
- **Frontend**: Nextjs, React
- **Backend**: FastAPI
- **Database**: Supabase
- **AI Tools**: Google Gemini, Groq (Llama 3.1 70B)
- **Build Tools**: Docker Compose
- **Libraries**: `genai`, `supabase`, `httpx`, `pydantic`, `dotenv`, `os`, `asyncio`

## 📦 Installation
To install the project, follow these steps:
1. Clone the repository: `git clone https://github.com/your-repo/vanshika-ai-persona.git`
2. Install the required dependencies: `pip install -r requirements.txt`
3. Set up the environment variables: `cp .env.example .env` and modify the `.env` file to include your API keys and other configuration settings.
4. Run the application: `uvicorn main:app --host 0.0.0.0 --port 8000`

## 💻 Usage
To use the application, follow these steps:
1. Start the application: `uvicorn main:app --host 0.0.0.0 --port 8000`
2. Open a web browser and navigate to `http://localhost:8000`
3. Interact with the AI persona using the chat interface.

## 📂 Project Structure
```markdown
.
├── apps
│   ├── voice
│   │   ├── main.py
│   │   ├── routers
│   │   │   ├── vapi.py
│   │   │   ├── chat.py
│   │   │   ├── calendar.py
│   │   ├── services
│   │   │   ├── rag.py
│   │   │   ├── persona.py
│   │   │   ├── llm.py
│   │   │   ├── calendar.py
├── packages
│   ├── rag
│   │   ├── main.py
│   │   ├── loader.py
│   │   ├── parser.py
│   │   ├── retriever.py
│   │   ├── indexer.py
│   │   ├── embedder.py
├── docker-compose.yml
└── README.md
```

## 📸 Screenshots

## 🤝 Contributing
To contribute to the project, please follow these steps:
1. Fork the repository: `git fork https://github.com/your-repo/vanshika-ai-persona.git`
2. Create a new branch: `git branch feature/your-feature`
3. Make your changes and commit them: `git commit -m "Your commit message"`
4. Push your changes to the remote repository: `git push origin feature/your-feature`
5. Create a pull request: `git pull-request`

## 📝 License
The project is licensed under the MIT License.

## 📬 Contact
For any questions or concerns, please contact us at [vanshikaagarwal781@gmail.com](mailto:vanshikaagarwal781@gmail.com).

## 💖 Thanks Message
This project was made possible by the contributions of many individuals. We would like to extend our gratitude to everyone who has contributed to the project.
