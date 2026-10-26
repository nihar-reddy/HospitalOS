# HospitalOS — Emergency Resource Coordination & Deadlock Recovery System

**An Operating Systems project demonstrating multithreading, synchronization, resource allocation, deadlock detection, and recovery through an interactive hospital emergency department simulation.**

## Overview

HospitalOS is an educational simulation that models how an emergency department coordinates limited resources while processing multiple patient workflows concurrently.

The system simulates patients requiring resources such as beds, ventilators, and procedure rooms. Multiple worker threads process treatment tasks, while synchronization mechanisms coordinate access to shared resources.

The project demonstrates how resource contention can lead to deadlock, how a deadlock can be detected, and how recovery techniques restore progress.

> **Disclaimer:** HospitalOS is an academic simulation developed for educational purposes. It is not intended for real-world clinical use or hospital decision-making.

## Objectives

- Demonstrate concurrent execution using real Python worker threads.
- Model limited resources and competing treatment workflows.
- Visualize resource allocation, resource requests, and circular waits.
- Detect deadlocks while distinguishing them from ordinary resource waiting.
- Demonstrate deadlock recovery through rollback or task termination.
- Illustrate synchronization, mutual exclusion, and safe resource management.

## Features

### 1. Emergency & Deadlock Lab

The emergency simulation models patients moving through treatment workflows while competing for limited resources.

Key features include:

- Configurable patient and resource capacities.
- Live resource allocation and availability monitoring.
- Interactive Resource Allocation Graph (RAG).
- Controlled deadlock injection for reproducible demonstrations.
- Deadlock detection and identification of blocked tasks.
- Recovery through rollback or termination of a selected task.
- Safe-state analysis and before-and-after recovery visualization.

### 2. Multithreading Lab

The multithreading interface demonstrates concurrent execution and worker coordination.

Key features include:

- Multiple Python worker threads processing patient tasks.
- Live thread states and task assignments.
- Visualization of running, waiting, blocked, and completed workflows.
- Execution timelines showing overlapping worker activity.
- Shared-resource synchronization and ownership tracking.
- Event logs describing important execution events.

## Operating Systems Concepts

| Concept | Implementation in HospitalOS |
|---|---|
| Multithreading | Multiple worker threads process treatment tasks concurrently. |
| Mutual exclusion | Shared resource state is protected using synchronization primitives. |
| Thread synchronization | `Condition`, `RLock`, `Barrier`, `Event`, and thread-safe queues coordinate execution. |
| Resource allocation | Beds, ventilators, and procedure rooms have configurable capacities. |
| Deadlock conditions | The simulation demonstrates mutual exclusion, hold-and-wait, no preemption, and circular wait. |
| Deadlock detection | Resource dependencies are analyzed to identify genuine deadlocked tasks. |
| Deadlock recovery | Rollback or termination releases resources and allows blocked work to progress. |
| Resource ordering | Normal workflows acquire resources in a consistent order to reduce circular-wait risk. |

### Deadlock Demonstration

The controlled deadlock scenario creates two treatment tasks that acquire different resources and then request resources held by one another.

This produces a circular dependency:

1. Task A holds a resource and requests a resource held by Task B.
2. Task B holds a resource and requests a resource held by Task A.
3. Both tasks become blocked because neither requested resource is available.
4. The detection mechanism identifies the deadlock.
5. Recovery releases the selected task's resources, allowing the remaining task to proceed.

The detector accounts for resource instances rather than assuming that every cycle necessarily represents a deadlock.

## Configuration

The simulation exposes five configurable parameters:

| Parameter | Purpose |
|---|---|
| Patients | Number of patient workflows in the simulation. |
| Beds | Available bed capacity. |
| Ventilators | Available ventilator capacity. |
| Procedure rooms | Available procedure-room capacity. |
| Worker threads | Number of treatment worker threads. |

Applying a new configuration resets and rebuilds the simulation so that resource allocations remain consistent.

## Technology Stack

**Frontend**
- React
- TypeScript
- Vite
- Tailwind CSS

**Backend**
- Python
- FastAPI
- WebSockets
- Python `threading` and synchronization primitives

**Testing**
- Pytest
- Python `unittest`

## Project Structure

```text
HospitalOS/
├── backend/
│   ├── main.py
│   ├── engine.py
│   ├── requirements.txt
│   └── tests/
│       ├── test_api.py
│       └── test_engine.py
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── App.tsx
│   │   ├── types.ts
│   │   └── useSim.ts
│   ├── package.json
│   └── vite.config.ts
├── .gitignore
└── README.md
```

## Installation and Setup

### Prerequisites

Install the following:

- Python 3.9 or later
- Node.js 18 or later
- npm
- Git (optional, for version control)

### 1. Start the Backend

Open a terminal in the project directory and run:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -m uvicorn main:app --reload --port 8000
```

The backend API will be available at:

- API: `http://127.0.0.1:8000`
- Interactive API documentation: `http://127.0.0.1:8000/docs`
- Live simulation state: `http://127.0.0.1:8000/api/state`

Keep this terminal running.

### 2. Start the Frontend

Open a second terminal and navigate to the project directory:

```bash
cd frontend
npm install
npm run dev
```

Open the frontend at:

**http://localhost:5173**

Keep both terminals running while using the application.

The frontend development server proxies API and WebSocket requests to the backend on port 8000.

## How to Demonstrate the Project

1. Launch the backend and frontend.
2. Open the Emergency & Deadlock interface.
3. Start the simulation and observe patient workflows competing for resources.
4. Open the Multithreading interface to inspect worker states and concurrent execution.
5. Reset the simulation and inject the controlled deadlock scenario.
6. Run deadlock detection and inspect the resource-allocation graph.
7. Select a victim task and demonstrate rollback or termination.
8. Observe resource release, the change in the dependency graph, and resumed execution.
9. Repeat with different resource capacities and worker counts.

## Running Tests

Activate the backend virtual environment, then run:

```bash
cd backend
source .venv/bin/activate
python3 -m pytest -v
```

Alternatively, use the Python standard-library test runner:

```bash
python3 -m unittest discover -s tests -v
```

The test suite covers resource constraints, concurrent execution, deadlock scenarios, detection, recovery, configuration, and API behavior.

## Limitations

- This is a controlled educational simulation, not a production hospital management system.
- Treatment tasks and resource requirements are simplified models.
- Simulated recovery represents operating-system-style task recovery, not clinical intervention.
- The system demonstrates selected deadlock management techniques; it does not model every behavior of a general-purpose operating system.

## Conclusion

HospitalOS connects core Operating Systems principles to a practical resource-coordination problem. By combining real worker threads, synchronized shared state, resource-allocation visualization, deadlock detection, and recovery, the project provides an interactive way to understand concurrency and resource management.

---

**Project:** HospitalOS — Emergency Resource Coordination & Deadlock Recovery System  
**Domain:** Operating Systems  
**Purpose:** Academic demonstration and learning
