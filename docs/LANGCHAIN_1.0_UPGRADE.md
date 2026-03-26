# LangChain 1.0 升级指南

## 概述

本项目已升级至 LangChain 1.0 (0.3.0+) 版本，使用了最新的 LangChain API 和 LangGraph 框架。

## 主要变化

### 1. 依赖版本更新

```txt
# 之前
langchain>=0.1.0
langchain-community>=0.0.10
langgraph>=0.0.20

# 现在
langchain>=0.3.0
langchain-community>=0.3.0
langchain-core>=0.3.0
langgraph>=0.2.0
```

### 2. 新增文件

- `src/core/rag_engine_langchain.py` - 使用 LangChain 1.0 API 的 RAG 引擎
- `src/chatbot/agent_langgraph.py` - 使用 LangGraph 的智能体

### 3. LangChain 1.0 新特性

#### LCEL (LangChain Expression Language)
使用新的链式语法构建应用：

```python
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

# 旧方式 (0.1.x)
chain = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type="stuff",
    retriever=retriever
)

# 新方式 (1.0)
chain = (
    {
        "context": retriever | RunnableLambda(format_docs),
        "input": RunnablePassthrough()
    }
    | prompt
    | llm
    | StrOutputParser()
)
```

#### LangGraph 状态图
使用 LangGraph 构建复杂的状态机：

```python
from langgraph.graph import StateGraph

# 定义状态
class AgentState(TypedDict):
    messages: List[Dict[str, str]]
    current_intent: Intent
    response: str

# 构建图
workflow = StateGraph(AgentState)
workflow.add_node("classify", classify_node)
workflow.add_node("route", route_node)
workflow.add_edge("classify", "route")
workflow.set_entry_point("classify")
graph = workflow.compile()
```

### 4. 模块化导入

```python
# 之前
from langchain import ...
from langchain.chains import ...
from langchain.vectorstores import ...

# 现在 (更模块化)
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStore
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.retrievers import BaseRetriever
from langchain.chains import create_retrieval_chain
from langchain_community.vectorstores import Milvus
```

## 使用指南

### 安装依赖

```bash
source venv/bin/activate
pip install -r requirements.txt
```

### 使用新 API

#### RAG 查询

```python
from src.core.rag_engine_langchain import get_rag_engine

# 获取 RAG 引擎
rag = get_rag_engine()

# 查询
result = rag.query("What are your working hours?")
print(result.answer)
print(f"Retrieval latency: {result.retrieval_latency:.3f}s")
```

#### LangGraph Agent

```python
from src.chatbot.agent_langgraph import get_chatbot_agent

# 获取智能体
agent = get_chatbot_agent()

# 处理消息
response = agent.process_message("I want to make a reservation")
print(response["response"])
print(f"Intent: {response['intent']}")
```

### 向后兼容

旧的实现仍然可用：

```python
# 使用旧的实现（自定义）
from src.chatbot.agent import get_simple_chatbot

chatbot = get_simple_chatbot()
response = chatbot.chat("What are your prices?")
```

## 架构对比

### 旧架构 (自定义实现)

```
用户输入 → 意图分类 → 处理器 → 响应生成 → Guardrails → 输出
```

### 新架构 (LangChain 1.0 + LangGraph)

```
┌─────────────────────────────────────────┐
│         LangGraph State Graph           │
│  ┌──────────┐    ┌──────────┐          │
│  │  Input   │───▶│Guardrails│          │
│  └──────────┘    └────┬─────┘          │
│                      │                  │
│                      ▼                  │
│              ┌───────────┐             │
│              │ Classify  │             │
│              │  Intent   │             │
│              └─────┬─────┘             │
│                    │                   │
│         ┌──────────┼──────────┐        │
│         ▼          ▼          ▼        │
│    ┌────────┐ ┌────────┐ ┌────────┐   │
│    │  RAG   │ │ Pricing│ │Reserve │   │
│    └───┬────┘ └───┬────┘ └───┬────┘   │
│        │          │          │        │
│        └──────────┼──────────┘        │
│                   ▼                   │
│          ┌──────────────┐             │
│          │Output Guards │             │
│          └──────┬───────┘             │
└─────────────────┼─────────────────────┘
                  │
                  ▼
              Response
```

## 迁移检查清单

- [x] 更新 requirements.txt
- [x] 创建新的 RAG 引擎使用 LangChain 1.0 API
- [x] 创建新的 Agent 使用 LangGraph
- [x] 保持向后兼容性
- [ ] 运行测试验证
- [ ] 更新文档

## 性能优化

LangChain 1.0 提供了更好的性能：

1. **流式处理**: 支持原生流式输出
2. **并行执行**: 自动并行化独立操作
3. **缓存**: 智能缓存减少重复计算
4. **批处理**: 支持批量查询优化

## 示例代码

完整的示例请参考：
- `src/core/rag_engine_langchain.py` - RAG 实现
- `src/chatbot/agent_langgraph.py` - Agent 实现
- `main.py` - 主程序入口

## 资源链接

- [LangChain 官方文档](https://python.langchain.com/)
- [LangGraph 文档](https://langchain-ai.github.io/langgraph/)
- [迁移指南](https://python.langchain.com/docs/version_migration/)
