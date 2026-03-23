# 🚗 Parking Space Reservation Chatbot

A RAG-based (Retrieval-Augmented Generation) intelligent chatbot for parking space reservation, built with Python, LangChain, LangGraph, and DeepSeek.

## Features

### Core Functionality
- **Information Retrieval**: Get answers about parking location, hours, pricing, rules, and amenities
- **Real-time Availability**: Check current parking space availability across different types
- **Reservation Booking**: Interactive collection of reservation data (name, license plate, dates, contact)
- **Dynamic & Static Data**: Separated storage for real-time data (SQLite) and static knowledge (vector DB)

### Advanced Features
- **RAG Architecture**: Combines vector similarity search with LLM generation for accurate responses
- **Guardrails & PII Protection**: Built-in PII detection and filtering to protect sensitive user data
- **Multi-turn Conversations**: Context-aware conversations with history management
- **Comprehensive Evaluation**: Performance metrics (Recall@K, Precision, NDCG) and latency tracking

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         User Interface                       │
│                        (CLI / Future Web UI)                 │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                    Chatbot Agent (LangGraph)                 │
│  ┌─────────────┐ ┌──────────────┐ ┌──────────────────────┐ │
│  │ Intent      │ │ Tool         │ │ State                │ │
│  │ Classifier  │ │ Execution    │ │ Management           │ │
│  └─────────────┘ └──────────────┘ └──────────────────────┘ │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
┌────────▼────────┐ ┌───▼────┐ ┌────────▼────────┐
│  RAG Engine     │ │ Guards │ │  Dynamic Data   │
│  ┌──────────┐   │ │        │ │  (SQLite DB)    │
│  │ Vector   │   │ │ PII    │ │  • Availability │
│  │ Store    │   │ │ Filter │ │  • Pricing      │
│  │ (Milvus) │   │ │        │ │  • Reservations │
│  └──────────┘   │ │        │ └─────────────────┘
│  ┌──────────┐   │ │ Topic  │
│  │ LLM      │   │ │ Filter │
│  │(DeepSeek)│   │ │        │
│  └──────────┘   │ └────────┘
└─────────────────┘ └────────────────┘
         │
         │
┌────────▼────────┐
│  Static Data    │
│  (Vector DB)    │
│  • Knowledge    │
│    Base         │
└─────────────────┘
```

## Project Structure

```
chatbot/
├── src/
│   ├── config/           # Configuration and settings
│   ├── core/             # RAG engine, vector store, LLM handler
│   ├── data/             # Data models, schemas, database operations
│   ├── guards/           # PII detection and guardrails
│   ├── chatbot/          # LangGraph agent and tools
│   └── evaluation/       # Metrics and performance testing
├── tests/                # Comprehensive test suite
├── data/                 # Knowledge base and database
├── docs/                 # Documentation and presentations
├── .github/workflows/    # CI/CD pipeline
├── main.py               # CLI entry point
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

## Installation

### Prerequisites
- Python 3.10 or higher
- pip or poetry for dependency management
- (Optional) Docker for Milvus vector database

### Setup Steps

1. **Clone the repository**
```bash
git clone <repository-url>
cd chatbot
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables**
```bash
cp .env.example .env
# Edit .env and add your DEEPSEEK_API_KEY
```

5. **Initialize the database**
```bash
python main.py --init-db
```

## Usage

### Running the Chatbot

Start the interactive CLI:
```bash
python main.py
```

### Example Conversation

```
🚗 CityCenter Parking Assistant

[You]: What are your working hours?
[Bot]: Our working hours are Monday-Friday: 6 AM - 11 PM,
       Saturday: 7 AM - 12 AM, Sunday: 8 AM - 10 PM.

[You]: How much does it cost to park?
[Bot]: Our rates start at $1.50/hour for motorcycles,
       $2.50/hour for compact spaces, and $3.00/hour for standard spaces.

[You]: I want to make a reservation
[Bot]: To make a reservation, I'll need some information.
       What's your first name?

[You]: John
[Bot]: Thank you! What's your last name?
```

### Commands

- `help` - Show available commands
- `stats` - Show session statistics
- `clear` - Clear conversation history
- `quit` - Exit the chatbot

## API Reference

### Core Components

#### RAGEngine
```python
from src.core.rag_engine import get_rag_engine

rag = get_rag_engine()
result = rag.query("What are your parking rates?")
print(result.answer)
```

#### ParkingTools
```python
from src.chatbot.tools import get_parking_tools

tools = get_parking_tools()
availability = tools.check_availability("standard")
pricing = tools.get_prices("compact")
```

#### GuardRailHandler
```python
from src.guards.railguard import get_guardrail_handler

guards = get_guardrail_handler()
processed_input, error = guards.process_input(user_input)
```

## Testing

### Run All Tests
```bash
pytest
```

### Run with Coverage
```bash
pytest --cov=src --cov-report=html
```

### Run Specific Test Module
```bash
pytest tests/test_rag_engine.py -v
```

### Test Structure
- `test_vector_store.py` - Vector store operations (6 tests)
- `test_rag_engine.py` - RAG pipeline and queries (10 tests)
- `test_guards.py` - PII detection and guardrails (12 tests)
- `test_chatbot.py` - Chatbot agent and tools (10 tests)
- `test_evaluation.py` - Metrics and performance (10 tests)

**Total**: 48+ tests covering all major components

## Evaluation

### Run Evaluation
```bash
# Retrieval metrics
python -m src.evaluation.metrics

# Performance benchmarks
python -m src.evaluation.performance
```

### Metrics Tracked
- **Precision@K**: Accuracy of retrieved documents
- **Recall@K**: Coverage of relevant documents
- **NDCG@K**: Ranking quality
- **MRR**: First relevant document position
- **Latency**: Response time measurements (p50, p95, p99)

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DEEPSEEK_API_KEY` | DeepSeek API key | Required |
| `LLM_PROVIDER` | LLM provider | deepseek |
| `LLM_BASE_URL` | LLM API base URL | https://api.deepseek.com |
| `DEFAULT_MODEL` | LLM model | deepseek-chat |
| `TEMPERATURE` | LLM temperature | 0.7 |
| `DATABASE_URL` | SQLite database path | sqlite:///./data/parking.db |

### Customization

Edit [src/config/settings.py](src/config/settings.py) to modify:
- LLM parameters (model, temperature, max tokens)
- Vector store settings (embedding model, chunk size)
- Database configuration
- Logging preferences

## Deployment

### Using Docker (Optional)

For production deployment with Milvus:
```bash
docker-compose up -d milvus
```

### CI/CD

The project includes GitHub Actions workflow for automated testing:
- Linting with ruff
- Type checking with mypy
- Running pytest with coverage

## Security & Privacy

### PII Protection
- **Presidio Integration**: Industry-standard PII detection
- **Redaction**: Automatic masking of sensitive data in outputs
- **Input Sanitization**: Protection against injection attacks

### Guardrails
- **Topic Filtering**: Stays within parking domain
- **Content Safety**: Blocks harmful content
- **Output Validation**: Ensures response quality

## Limitations & Future Work

### Current Limitations
- Mock RAG engine for demo reliability (Milvus setup optional)
- CLI interface only (web UI planned)
- Human-in-the-loop confirmation not automated

### Planned Enhancements
- [ ] Web UI with Streamlit or Gradio
- [ ] Email/SMS notifications for reservations
- [ ] Payment gateway integration
- [ ] Admin dashboard for reservation management
- [ ] Multi-language support

## Troubleshooting

### Common Issues

**Problem**: `ANTHROPIC_API_KEY not found`
- **Solution**: Set the API key in `.env` file or environment variables

**Problem**: Milvus connection failed
- **Solution**: The app will use in-memory vector store as fallback

**Problem**: Tests fail with import errors
- **Solution**: Ensure dependencies are installed: `pip install -r requirements.txt`

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

MIT License - see LICENSE file for details

## Authors

Parking Chatbot Development Team

## Acknowledgments

- DeepSeek for LLM API
- LangChain/LangGraph for framework
- Presidio for PII detection
- Milvus for vector database

---

For questions or support, please open an issue on GitHub.
