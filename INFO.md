                    USER
                      │
                      ▼
              ┌──────────────┐
              │ Orchestrator │
              │   (System)   │
              └──────┬───────┘
                     │
              ส่งงานให้ Agent
                     │
       ┌─────────────┼─────────────┐
       ▼             ▼             ▼
    Agent A       Agent B       Agent C
       │             │             │
       └─────────────┼─────────────┘
                     │
                Agent Debate
                     │
                     ▼
                Task Graph

User
 │
 ▼
Orchestrator
 │
 ▼
Task
 │
 ▼
Agent Network
 │
 ├───────────────┐
 │               │
 ▼               ▼
Agent A  <----> Agent B
   ▲               │
   │               │
   └──── Agent C <-┘

Agent เสนอ งาน
Orchestrator อนุมัติ/จัดการ lifecycle

นี่ทำให้ autonomous แต่ยังควบคุมได้

                 Agent
                   │
             "ฉันอยากทำ X"
                   │
                   ▼
             Orchestrator
                   │
          ┌────────┼────────┐
          │        │        │
       Budget    State    Policy
          │        │        │
          └────────┼────────┘
                   │
             APPROVE / DENY
                   │
                   ▼
                Execute


Orchestrator มีหน้าที่แค่:
    ส่ง message
    เก็บ state
    ตรวจ permission
    จัดการ timeout
    เก็บ artifact
    ป้องกัน loop
    คุม token budget

Agent จะสร้าง Task กันเอง



                    ┌─────────────────────┐
                    │     ORCHESTRATOR    │
                    │                     │
                    │ State               │
                    │ Task Graph          │
                    │ Permissions         │
                    │ Budget              │
                    │ Timeout             │
                    │ Validation          │
                    └──────────┬──────────┘
                               │
                       MessageBus
                               │
             ┌─────────────────┼─────────────────┐
             │                 │                 │
             ▼                 ▼                 ▼
        ┌─────────┐       ┌─────────┐       ┌─────────┐
        │ Agent 01│       │ Agent 02│       │ Agent 03│
        │         │       │         │       │         │
        │ research│       │ python  │       │ security│
        │ analysis│       │ coding  │       │ testing │
        │ web     │       │ debug   │       │ analysis│
        └─────────┘       └─────────┘       └─────────┘
             │                 │                 │
             └─────────────────┼─────────────────┘
                               │
                         Provider Layer
                               │
                ┌──────────────┴──────────────┐
                │                             │
             Groq Pool                   OpenRouter