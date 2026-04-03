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

### 🆕 Stage 2: Human-in-the-Loop Administrator System
- **Admin Approval Workflow**: Reservation requests are automatically escalated to human administrators for approval
- **Multi-Channel Notifications**: Support for email, REST API/webhook, and mock channels (for testing)
- **Administrator CLI**: Interactive command-line interface for managing reservations
- **Status Tracking**: Real-time status updates (pending, approved, rejected, expired)
- **REST API Server**: FastAPI-based server for receiving admin responses and webhook notifications
- **Request Expiration**: Automatic expiration of pending requests after 24 hours (configurable)
- **User Notifications**: Users receive clear feedback about their reservation status

### 🆕 Stage 3: MCP Server for Persistent Storage
- **MCP Protocol Implementation**: FastAPI-based MCP server for managing approved reservations
- **File Storage**: Automatically writes approved reservations to text file in format: `Name | Car Number | Reservation Period | Approval Time`
- **Security Features**: API key authentication, input validation, file size limits
- **Backup System**: Automatic backup of reservation files before modifications
- **Search Functionality**: Query reservations by name or car number
- **Statistics API**: Get file statistics and reservation counts
- **Integration**: Automatically called when administrator approves a reservation

### 🆕 Stage 4: LangGraph System Orchestration
- **Unified Workflow**: Complete orchestration of all stages (1-3) using LangGraph
- **State Management**: Centralized state management across all components
- **Workflow Nodes**: 8 specialized nodes for each stage of the pipeline
- **Conditional Routing**: Intelligent routing based on conversation type and state
- **Memory Checkpoints**: Conversation persistence with LangGraph MemorySaver
- **End-to-End Testing**: Comprehensive integration and load testing
- **Performance**: Average response time < 1s for information queries
- **Security Features**: API key authentication, input validation, file size limits
- **Backup System**: Automatic backup of reservation files before modifications
- **Search Functionality**: Query reservations by name or car number
- **Statistics API**: Get file statistics and reservation counts
- **Integration**: Automatically called when administrator approves a reservation

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         User Interface                       │
│                        (CLI / Future Web UI)                 │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│              Chatbot Agent & Escalation System              │
│  ┌─────────────┐ ┌──────────────┐ ┌──────────────────────┐ │
│  │ Intent      │ │ Tool         │ │ Escalation Manager   │ │
│  │ Classifier  │ │ Execution    │ │ • Request Creation   │ │
│  └─────────────┘ └──────────────┘ │ • Channel Handlers   │ │
│  ┌─────────────┐ ┌──────────────┐ │ • Status Tracking    │ │
│  │ Admin       │ │ Notification │ └──────────────────────┘ │
│  │ Agent       │ │ System       │                            │
│  └─────────────┘ └──────────────┘                            │
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
│  └──────────┘   │ │        │ │  • Requests     │
│  ┌──────────┐   │ │ Topic  │ └─────────────────┘
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

         ▼
┌──────────────────────────────────────────────────┐
│          Administrator Interface                  │
│  ┌──────────────┐ ┌─────────────┐ ┌───────────┐ │
│  │ Admin CLI    │ │ REST API    │ │ Email/Webhook│ │
│  └──────────────┘ └─────────────┘ └───────────┘ │
└──────────────────────────────────────────────────┘
```

## Project Structure

```
chatbot/
├── src/
│   ├── config/           # Configuration and settings
│   ├── core/             # RAG engine, vector store, LLM handler
│   ├── data/             # Data models, schemas, database operations
│   │   ├── schemas.py            # Pydantic models
│   │   ├── static_data.py        # Knowledge base loader
│   │   ├── dynamic_data.py       # SQLite operations
│   │   ├── reservation_state.py  # 🆕 Reservation state models
│   │   └── reservation_manager.py # 🆕 Reservation CRUD operations
│   ├── guards/           # PII detection and guardrails
│   ├── chatbot/          # LangGraph agent and tools
│   │   ├── agent.py              # Main chatbot agent
│   │   ├── tools.py              # Parking tools
│   │   ├── admin_agent.py        # 🆕 Administrator agent
│   │   ├── channels.py           # 🆕 Communication channel handlers
│   │   └── escalation.py         # 🆕 Escalation manager
│   ├── api/              # 🆕 REST API server
│   │   └── server.py             # FastAPI endpoints
│   ├── mcp/              # 🆕 MCP Server
│   │   └── server.py             # MCP server for file storage
│   ├── orchestration/    # 🆕 LangGraph orchestration
│   │   └── graph.py             # Unified workflow orchestration
│   └── evaluation/       # Metrics and performance testing
├── tests/                # Comprehensive test suite
│   ├── test_admin_system.py      # 🆕 Admin system tests
│   ├── test_mcp_server.py        # 🆕 MCP server tests
│   ├── test_orchestration_basic.py # 🆕 Orchestration tests
│   └── integration_test.py       # 🆕 Integration tests
├── data/                 # Knowledge base and database
├── docs/                 # Documentation and presentations
├── .github/workflows/    # CI/CD pipeline
├── main.py               # Original CLI entry point
├── main_orchestrated.py  # 🆕 Unified entry point with orchestration
├── admin_cli.py          # 🆕 Administrator CLI
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

**Option 1: Full LangGraph Orchestration (Recommended)**
```bash
python main_orchestrated.py
# or
python -m src.orchestration.graph
```

This mode provides:
- Complete workflow orchestration
- State management across all components
- Automatic escalation and approval tracking
- MCP server integration

**Option 2: Simple Chatbot**
```bash
python main.py
# or
python main_orchestrated.py --simple
```

**Option 3: Administrator Console**
```bash
python main_orchestrated.py --admin
# or
python admin_cli.py
```

**Option 4: Integration Tests**
```bash
python main_orchestrated.py --test
# or
python tests/integration_test.py
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

### 🆕 Administrator Console

Manage reservation approvals through the administrator CLI:

```bash
# Start the administrator console
python admin_cli.py
```

#### Admin Commands

```
🔧 admin> list              # List all pending reservations
🔧 admin> details <id>      # Get reservation details
🔧 admin> approve <id>      # Approve a reservation
🔧 admin> reject <id>       # Reject a reservation
🔧 admin> stats             # Show statistics
🔧 admin> cleanup           # Clean up expired requests
🔧 admin> help              # Show help
🔧 admin> quit              # Exit
```

#### REST API Server

For webhook integrations and programmatic access:

```bash
# Start the API server
python -m src.api.server
```

The API server provides:
- `POST /webhook/reservation` - Receive reservation notifications
- `POST /api/admin/respond` - Handle admin approval/rejection
- `GET /api/reservations/{id}` - Get reservation details
- `GET /api/reservations` - List pending reservations
- `GET /api/stats` - Get statistics
- `POST /api/cleanup` - Clean up expired reservations

API documentation: `http://localhost:8000/docs`

#### MCP Server

For persistent storage of approved reservations:

```bash
# Start the MCP server (runs on port 8001)
python -m src.mcp.server
```

The MCP server provides:
- `POST /mcp/tool/write_reservation` - Write approved reservation to file
- `POST /mcp/tool/read_reservations` - Read all or search reservations
- `GET /mcp/tool/storage_stats` - Get file statistics
- `DELETE /mcp/tool/all_reservations` - Delete all reservations (with backup)
- `POST /mcp/execute` - Generic tool execution endpoint

**File Format:**
```
Name | Car Number | Reservation Period | Approval Time
```

**Example:**
```
John Doe | ABC-123 | 2026-04-10 10:00 - 2026-04-10 12:00 | 2026-04-10 09:15:30
Jane Smith | XYZ-789 | 2026-04-10 14:00 - 2026-04-10 16:00 | 2026-04-10 13:20:45
```

**Security:**
- API key authentication (set via `MCP_API_KEY` environment variable)
- Input validation and sanitization
- File size limits (configurable via `MAX_FILE_SIZE`)
- Automatic backup before modifications

**Integration:**
The MCP server is automatically called when an administrator approves a reservation through:
- Admin CLI (`admin_cli.py`)
- REST API (`/api/admin/respond`)
- Direct function call (`save_approved_reservation()`)

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

### 🆕 Stage 2: Administrator System

#### ReservationManager
```python
from src.data.reservation_manager import get_reservation_manager

manager = get_reservation_manager()

# Create a reservation request
request = manager.create_reservation_request(
    user_name="John",
    user_surname="Doe",
    car_number="ABC-123",
    start_time=datetime(2026, 4, 10, 10, 0),
    end_time=datetime(2026, 4, 10, 12, 0),
    space_type="standard",
    contact_info="john@example.com",
)

# Approve reservation
manager.approve_reservation(request.reservation_id, admin_note="Approved!")

# Get pending reservations
pending = manager.get_pending_reservations()
```

#### EscalationManager
```python
from src.chatbot.escalation import get_escalation_manager

escalation = get_escalation_manager()

# Submit reservation to admin
result = escalation.escalate_reservation(
    user_name="John",
    user_surname="Doe",
    car_number="ABC-123",
    start_time=datetime(2026, 4, 10, 10, 0),
    end_time=datetime(2026, 4, 10, 12, 0),
    space_type="standard",
    contact_info="john@example.com",
)

# Check status
status = escalation.check_reservation_status(result["reservation_id"])
```

#### AdminAgent
```python
from src.chatbot.admin_agent import get_admin_agent

admin = get_admin_agent()

# List pending reservations
response = admin.process_message("list")

# Approve a reservation
response = admin.process_message("approve abc-123 Looks good!")

# Reject a reservation
response = admin.process_message("reject abc-123 Space unavailable")

# Get statistics
response = admin.process_message("stats")
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
| **Admin System** | | |
| `ADMIN_EMAIL` | Administrator email address | admin@example.com |
| `SMTP_SERVER` | SMTP server for email notifications | smtp.gmail.com |
| `SMTP_PORT` | SMTP port | 587 |
| `SMTP_USERNAME` | SMTP username | - |
| `SMTP_PASSWORD` | SMTP password | - |
| `ADMIN_API_ENDPOINT` | Webhook endpoint for REST API | - |
| `ADMIN_API_KEY` | API key for authentication | - |
| **MCP Server** | | |
| `MCP_API_KEY` | MCP server API key for authentication | - |
| `RESERVATION_FILE` | Path to approved reservations file | ./data/approved_reservations.txt |
| `BACKUP_DIR` | Directory for backup files | ./data/backups |
| `MAX_FILE_SIZE` | Maximum file size in bytes | 10485760 (10MB) |
| `ENABLE_BACKUP` | Enable automatic backups | true |
| `REQUIRE_AUTH` | Require API key authentication | true |

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
