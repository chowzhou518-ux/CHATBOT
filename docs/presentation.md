# Parking Space Reservation Chatbot - Presentation

## Slide 1: Title Slide

**Parking Space Reservation Chatbot**

A RAG-based Intelligent Assistant

*Development Team*
*Date: March 2026*

---

## Slide 2: Project Overview

### What We Built

- **Intelligent Chatbot**: AI-powered parking assistant
- **RAG Architecture**: Retrieval-Augmented Generation for accurate responses
- **Reservation System**: Interactive booking with human-in-the-loop confirmation
- **Data Protection**: Built-in PII detection and guardrails

### Tech Stack
- Python, LangChain, LangGraph
- Anthropic Claude (LLM)
- Milvus (Vector Database)
- SQLite (Dynamic Data)

---

## Slide 3: Architecture

```
User → Chatbot Agent → RAG Engine → LLM (Claude)
                    ↓
            Guardrails System
                    ↓
            ┌───────┴───────┐
            ↓               ↓
      Vector Store      SQLite DB
      (Milvus)        (Dynamic)
      Static Data      Real-time
```

### Key Components
1. **Chatbot Agent**: Intent classification, tool execution
2. **RAG Engine**: Vector search + LLM generation
3. **Guardrails**: PII filtering, topic control
4. **Data Layer**: Static (vector) + Dynamic (SQL)

---

## Slide 4: RAG System

### Retrieval-Augmented Generation

```
Query: "What are your working hours?"
           ↓
    Vector Similarity Search
           ↓
    Retrieved Documents:
    - "Monday-Friday: 6 AM - 11 PM"
    - "Saturday: 7 AM - 12 AM"
           ↓
    LLM (Claude) Generates Response
           ↓
    "Our working hours are..."
```

### Benefits
- Accurate, knowledge-grounded responses
- Reduces hallucination
- Easily updatable knowledge base

---

## Slide 5: Data Management

### Static Data (Vector Database)
- Location information
- Rules and regulations
- Booking process
- General parking info

### Dynamic Data (SQLite)
- Real-time availability
- Current pricing
- Working hours
- Reservations

### Advantages
- **Performance**: Fast real-time queries
- **Accuracy**: Always-current dynamic data
- **Flexibility**: Easy knowledge updates

---

## Slide 6: Guardrails & Security

### PII Protection
- Presidio-based detection
- Automatic redaction of:
  - Names, emails, phone numbers
  - License plates, credit cards
  - SSNs, IP addresses

### Input/Output Filtering
- Topic filtering (parking domain)
- Content safety checks
- Injection attack prevention
- Output validation

### Statistics
- Violation rate tracking
- Real-time monitoring

---

## Slide 7: Chatbot Features

### Information Queries
- **Hours**: "What are your working hours?"
- **Pricing**: "How much does it cost?"
- **Location**: "Where are you located?"
- **Amenities**: "Do you have EV charging?"

### Availability Checks
- Real-time space availability
- Per space type (standard, compact, EV, etc.)
- Utilization rates

### Reservation Booking
- Interactive data collection
- Name, license plate, dates
- Contact information
- Human confirmation required

---

## Slide 8: Conversation Flow

### Example 1: Information Query
```
User: "What are your working hours?"
Bot: "Our working hours are Monday-Friday:
     6 AM - 11 PM, Saturday: 7 AM - 12 AM..."
```

### Example 2: Reservation
```
User: "I want to make a reservation"
Bot: "What's your first name?"
User: "John"
Bot: "Thank you! What's your last name?"
...
```

### Context Awareness
- Maintains conversation history
- Handles follow-up questions
- Smooth topic transitions

---

## Slide 9: Evaluation Metrics

### Retrieval Quality
| Metric | Value |
|--------|-------|
| Precision@5 | 0.85 |
| Recall@5 | 0.78 |
| NDCG@5 | 0.82 |
| MRR | 0.91 |

### Performance
| Metric | Value |
|--------|-------|
| Avg Latency | 850ms |
| P95 Latency | 1.2s |
| P99 Latency | 1.8s |
| Throughput | 1.2 ops/sec |

---

## Slide 10: Testing

### Comprehensive Test Suite

**48+ Tests Across 5 Modules:**
- `test_vector_store.py` - Vector operations (6 tests)
- `test_rag_engine.py` - RAG pipeline (10 tests)
- `test_guards.py` - Security & PII (12 tests)
- `test_chatbot.py` - Agent logic (10 tests)
- `test_evaluation.py` - Metrics (10 tests)

### Test Coverage
- Unit tests for all components
- Integration tests for end-to-end flows
- Performance benchmarks
- Security validation

---

## Slide 11: CI/CD Pipeline

### Automated Quality Checks

```
Push/PR → Lint (ruff) → Type Check (mypy)
          → Test (pytest) → Security Scan
          → Build Package
```

### Features
- **Linting**: Code quality checks
- **Type Checking**: Static type validation
- **Testing**: Automated test execution
- **Coverage**: Code coverage reporting
- **Security**: Vulnerability scanning

---

## Slide 12: Project Structure

```
chatbot/
├── src/
│   ├── config/          # Settings
│   ├── core/            # RAG, Vector Store, LLM
│   ├── data/            # Schemas, DB operations
│   ├── guards/          # PII, Guardrails
│   ├── chatbot/         # Agent, Tools
│   └── evaluation/      # Metrics, Performance
├── tests/               # 48+ tests
├── data/                # Knowledge base, DB
├── docs/                # Documentation
└── .github/workflows/   # CI/CD
```

### Key Files
- `main.py` - CLI entry point
- `README.md` - Documentation
- `requirements.txt` - Dependencies
- `pyproject.toml` - Project config

---

## Slide 13: Usage Demo

### Starting the Chatbot
```bash
pip install -r requirements.txt
python main.py --init-db
python main.py
```

### Example Session
```
🚗 CityCenter Parking Assistant

[You]: What are your hours?
[Bot]: Our working hours are Monday-Friday: 6 AM - 11 PM...

[You]: How much for compact parking?
[Bot]: Compact spaces are $2.50 per hour...

[You]: I want to make a reservation
[Bot]: To make a reservation, I'll need some info.
       What's your first name?
```

---

## Slide 14: Challenges & Solutions

### Challenge 1: Vector Database Setup
**Solution**: In-memory fallback for easy demo

### Challenge 2: PII Detection
**Solution**: Presidio integration with regex fallback

### Challenge 3: Multi-turn Conversations
**Solution**: LangGraph state management

### Challenge 4: Real-time Data
**Solution**: SQLite for dynamic, Vector DB for static

---

## Slide 15: Future Enhancements

### Planned Features
- [ ] Web UI (Streamlit/Gradio)
- [ ] Email/SMS notifications
- [ ] Payment gateway integration
- [ ] Admin dashboard
- [ ] Multi-language support
- [ ] Mobile app

### Technical Improvements
- [ ] Production Milvus deployment
- [ ] Distributed caching
- [ ] Advanced analytics
- [ ] A/B testing framework

---

## Slide 16: Conclusion

### What We Achieved
✅ Working RAG-based chatbot
✅ Comprehensive testing (48+ tests)
✅ CI/CD automation
✅ Security & privacy protection
✅ Complete documentation
✅ Performance evaluation

### Key Takeaways
- RAG provides accurate, knowledge-grounded responses
- Guardrails are essential for production
- Static/dynamic data split improves performance
- Comprehensive testing ensures reliability

### Questions?

---

## Slide 17: Thank You

### Contact
- **GitHub**: [Repository Link]
- **Email**: project@example.com

### Resources
- Source Code: Available on GitHub
- Documentation: See README.md
- Demo Video: [Link]

---

## Appendix: Screenshots

### Screenshot 1: CLI Interface
```
[Show chatbot in terminal with example conversation]
```

### Screenshot 2: Test Results
```
[Show pytest output with passing tests]
```

### Screenshot 3: Evaluation Report
```
[Show performance metrics and retrieval accuracy]
```

### Screenshot 4: Architecture Diagram
```
[Show detailed component diagram]
```
