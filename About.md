ฉันกำลังพัฒนาโปรเจกต์ Python ชื่อ `Agent_worker` เป็นระบบ Dynamic Multi-Agent Collaboration สำหรับใช้งานจริง

เป้าหมายของระบบคือให้ AI Agents หลายตัวสามารถทำงานร่วมกันแบบ dynamic โดยไม่มี fixed role เช่น ไม่กำหนดตายตัวว่า agent_01 = researcher, agent_02 = coder, agent_03 = reviewer

แต่ละ Agent มีเพียง `capabilities` และสามารถตัดสินใจเองตาม task ว่าควร:

* WORK
* DELEGATE
* ASK
* COMPLETE
* REJECT

ระบบต้องสามารถ:

1. รับ task จาก user
2. ให้ Agent วิเคราะห์ task
3. แตก task เป็น subtasks แบบ dynamic
4. เลือก Agent อื่นตาม capabilities
5. ส่ง task ผ่าน MessageBus
6. Agent รับงานและทำงาน
7. ส่ง RESULT กลับ
8. ส่งผลให้ Agent อื่น REVIEW
9. ถ้า review ไม่ผ่าน ให้ REWORK
10. ถ้าทุก subtask เสร็จ ให้รวมผลกลับเป็น parent task
11. ทำงานต่อจน root task COMPLETED หรือ FAILED
12. มี budget/depth/review limit เพื่อป้องกัน infinite loop
13. ในอนาคตต้องรองรับ tools จริง เช่น Python, Web, HTTP, Git, Shell, File System, Docker ฯลฯ
14. Agent ไม่ควรมีสิทธิ์ควบคุมระบบโดยตรง แต่ควรเสนอ action และให้ Orchestrator เป็นผู้ validate/execute

IMPORTANT ARCHITECTURE:

Agent != Model

Agent ประกอบด้วย:

* agent_id
* capabilities
* provider/model
* memory/context
* tools
* state
* message interface

แต่ role ไม่ควรถูกกำหนดแบบตายตัว

Orchestrator เป็น system component ไม่ใช่ Manager Agent

Orchestrator มีหน้าที่:

* lifecycle/state management
* task graph
* validation
* routing
* permissions
* budget
* timeout
* retry
* loop prevention
* review flow
* result aggregation

Agent เป็นผู้ตัดสินใจเชิงงาน ส่วน Orchestrator เป็นผู้ควบคุม runtime และ enforce policy

CURRENT PROJECT STRUCTURE:

Agent_worker/
├── main.py
├── .env
├── .gitignore
├── requirements.txt
│
├── config/
│   └── settings.py
│
├── providers/
│   ├── **init**.py
│   ├── base.py
│   └── groq.py
│
└── core/
├── **init**.py
├── agent.py
├── decision.py
├── message_bus.py
├── network.py
├── orchestrator.py
├── protocol.py
├── task.py
└── task_graph.py

CURRENT AGENTS:

agent_01:

* research
* analysis
* web

agent_02:

* python
* programming
* debugging

agent_03:

* security
* testing
* analysis

MODEL:

Groq API

Default model:
`openai/gpt-oss-20b`

มี Groq API keys 4 ตัว

Environment:

GROQ_API_KEY_1=...
GROQ_API_KEY_2=...
GROQ_API_KEY_3=...
GROQ_API_KEY_4=...

GROQ_MODEL=openai/gpt-oss-20b

MAX_TASKS=30
MAX_DEPTH=4
MAX_REVIEW_ROUNDS=2

IMPORTANT CURRENT ISSUE:

ตอนนี้ฉันทดสอบระบบแล้วพบ error:

`AsyncCompletions.create() got an unexpected keyword argument 'reasoning_effort'`

สาเหตุคือ Groq SDK version ที่ติดตั้งอยู่ไม่รองรับ `reasoning_effort`

ดังนั้นใน `providers/groq.py` ได้แก้โดยเอา:

`reasoning_effort="medium"`

ออกจากทั้ง `generate()` และ `generate_structured()`

ห้ามใส่ parameter นี้กลับเข้ามา เว้นแต่ตรวจสอบ version/API ของ SDK ก่อน

CURRENT FLOW:

ก่อนแก้ architecture ระบบทำ:

User Task
↓
Orchestrator
↓
TASK_OFFER ไป agent_01
TASK_OFFER ไป agent_02
TASK_OFFER ไป agent_03

ซึ่งไม่ตรงกับ architecture ที่ต้องการ เพราะทุก Agent ได้รับ root task พร้อมกัน

ฉันต้องการเปลี่ยนเป็น:

User Task
↓
Orchestrator
↓
Initial Agent
↓
Agent DECISION
├── WORK
├── DELEGATE
├── ASK
├── COMPLETE
└── REJECT

ตัวอย่าง:

ROOT TASK
↓
agent_01
↓
DELEGATE
├── research subtask → agent_01
├── implementation → agent_02
└── security testing → agent_03
↓
RESULT
↓
REVIEW
↓
PASS / REWORK
↓
Aggregate
↓
ROOT COMPLETE

CURRENT DECISION MODEL:

```python
class DecisionType(str, Enum):
    WORK = "WORK"
    DELEGATE = "DELEGATE"
    ASK = "ASK"
    COMPLETE = "COMPLETE"
    REJECT = "REJECT"


class ProposedSubtask(BaseModel):
    description: str
    required_capabilities: list[str] = []
    target_agent: str | None = None


class AgentDecision(BaseModel):
    decision: DecisionType
    reason: str
    confidence: float
    subtasks: list[ProposedSubtask] = []
    target_agent: str | None = None
    result: str | None = None
```

CURRENT TASK MODEL:

```python
class TaskStatus(str, Enum):
    CREATED = "CREATED"
    PROPOSED = "PROPOSED"
    ACCEPTED = "ACCEPTED"
    RUNNING = "RUNNING"
    REVIEW = "REVIEW"
    REWORK = "REWORK"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Task(BaseModel):
    task_id: str
    parent_task_id: str | None
    description: str
    required_capabilities: list[str]
    created_by: str | None
    assigned_agent: str | None
    reviewer_agent: str | None
    status: TaskStatus
    result: Any | None
    review_result: Any | None
    metadata: dict
    children: list[str]
    attempts: int
    review_round: int
    max_attempts: int
```

CURRENT MESSAGE TYPES:

```python
class MessageType(str, Enum):
    TASK_OFFER = "TASK_OFFER"
    TASK_ACCEPTED = "TASK_ACCEPTED"
    TASK_REJECTED = "TASK_REJECTED"
    TASK_RESULT = "TASK_RESULT"
    REVIEW_REQUEST = "REVIEW_REQUEST"
    REVIEW_RESULT = "REVIEW_RESULT"
    SUBTASK_CREATED = "SUBTASK_CREATED"
    QUESTION = "QUESTION"
    ANSWER = "ANSWER"
    ERROR = "ERROR"
```

CURRENT MESSAGE BUS:

เป็น in-memory asyncio Queue:

Agent
↓
MessageBus
↓
Agent

ตอนนี้ยังไม่มี Redis/NATS และยังไม่ต้องรีบเปลี่ยนจนกว่า core runtime จะ stable

CURRENT TASK GRAPH:

มี:

* parent_task_id
* children
* create_subtask()
* all_children_completed()
* get_depth()
* root task

ใช้สำหรับ dynamic decomposition

CURRENT ORCHESTRATOR:

มีหน้าที่:

* create root task
* offer task
* handle delegation
* submit result
* choose reviewer
* submit review
* rework
* complete task
* aggregate child results
* handle rejection
* handle question
* enforce max_tasks
* enforce max_depth
* enforce max_review_rounds

CURRENT AGENT:

Agent สามารถ:

* inspect capabilities
* inspect other agents
* decide()
* work()
* execute()
* review()
* send()
* receive()
* run()

Agent decision ใช้ Groq Structured Output

CURRENT PROVIDER:

`GroqProvider` ใช้:

```python
AsyncGroq(api_key=...)
```

มี:

* generate()
* generate_structured()

`generate_structured()` ใช้ JSON Schema และ parse ด้วย `json.loads()`

IMPORTANT:

อย่าออกแบบระบบใหม่ทั้งหมด

ให้ continue จาก architecture นี้

ถ้าพบว่าการออกแบบปัจจุบันมี bug ให้แก้เฉพาะส่วนที่จำเป็น และอธิบายว่าแก้เพราะอะไร

NEXT GOAL:

ฉันต้องการทำให้ระบบนี้ "ใช้งานจริง" มากขึ้น

ลำดับที่ต้องการพัฒนาต่อ:

PHASE 1:
ทำ core multi-agent loop ให้ stable ก่อน

ต้องมี:

User Task
→ Initial Agent
→ Decision
→ Dynamic Task Decomposition
→ Task Assignment
→ Agent Execution
→ Result
→ Independent Review
→ Rework
→ Aggregation
→ Final Result

PHASE 2:
สร้าง Tool System

ตัวอย่าง tools:

* Python execution
* HTTP client
* Web search
* File read/write
* Git
* Shell
* Docker
* Database

แต่ Tool ต้องมี permission system

ห้ามให้ LLM execute shell หรือ arbitrary code โดยตรงโดยไม่มี policy

PHASE 3:
Memory

แยก:

* short-term task context
* agent memory
* shared project memory
* artifact storage

ไม่ควรส่ง conversation ทั้งหมดทุกครั้ง เพราะจะเปลือง token

PHASE 4:
Production Runtime

เพิ่ม:

* persistent task state
* Redis/NATS message bus
* PostgreSQL/SQLite
* idempotency
* retry
* timeout
* cancellation
* structured logging
* metrics
* tracing
* token budget
* per-agent budget
* provider rate limiter
* provider fallback

PHASE 5:
Provider Pool

มี Groq 4 accounts และ OpenRouter

แต่ห้ามออกแบบระบบเพื่อ bypass provider rate limits

ให้ทำเป็น provider abstraction + rate limiter + health state + fallback

เช่น:

ProviderPool
├── Groq #1
├── Groq #2
├── Groq #3
├── Groq #4
└── OpenRouter

Agent ไม่ควรรู้ว่า key ไหนถูกใช้

PHASE 6:
Real Tools / Autonomous Engineering

สุดท้ายต้องการให้ Agent สามารถทำงานจริง เช่น:

User:
"Build a Python HTTP security header scanner"

ระบบควรสามารถ:

1. วิเคราะห์ requirement
2. แตก task
3. research
4. implement
5. run tests
6. review code
7. fix bugs
8. run tests ใหม่
9. inspect result
10. สรุป final output

โดยสามารถสร้างและแก้ไฟล์จริงใน workspace ได้

DESIGN PRINCIPLES:

1. ไม่มี fixed roles
2. Capability-based collaboration
3. Agent เป็น autonomous worker
4. Orchestrator เป็น runtime controller
5. Structured messages
6. Structured decisions
7. Task graph
8. Independent review
9. Explicit permissions
10. Budget limits
11. Loop prevention
12. Observable execution
13. Provider abstraction
14. Tools แยกออกจาก Agent logic
15. อย่าให้ LLM ควบคุม infrastructure โดยตรง

เวลาตอบ:

* ให้ code ที่ copy ไปใช้ได้จริง
* ระบุชื่อไฟล์ชัดเจน
* ถ้าต้องแก้ไฟล์เดิม ให้ส่งไฟล์ฉบับเต็ม ไม่ใช่แค่ snippet ถ้าการแก้มีหลายจุด
* อย่าเขียน architecture ใหม่โดยไม่จำเป็น
* อธิบายเหตุผลของ design สำคัญ ๆ สั้น ๆ
* เน้นให้ระบบรันได้จริงก่อน แล้วค่อยเพิ่มความซับซ้อน
* ถ้ามี API/SDK ที่อาจเปลี่ยนตาม version ให้ตรวจสอบก่อนแนะนำ syntax
* อย่าใส่ `reasoning_effort` ใน Groq request เพราะ SDK ปัจจุบันที่เครื่องนี้ใช้อยู่ไม่รองรับ
* ถ้าแก้ bug ให้บอกว่าเกิดจากอะไร
* อย่าข้ามขั้นตอนสำคัญ
* อย่าทำ mock architecture ที่ไม่ได้เชื่อมกับ runtime จริง

เริ่มทำต่อจากระบบปัจจุบันได้เลย โดยเป้าหมายแรกคือทำให้ Core Multi-Agent Loop ทำงานครบและ stable ก่อนเข้าสู่ Tool System
