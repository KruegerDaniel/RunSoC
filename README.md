# RunSoC: An Allocation Framework for Automotive Software Components to Semiconductor Design Partitions in System-on-Chips



## Overview



**RunSoC** is a specialized engineering framework designed for scheduling and allocation of automotive software components on multi-core SoCs. RunSoC integrates static and dynamic strategies to improve core utilization and task latency.



Automotive systems are transitioning from traditional microcontroller-based designs to high‑performance, multi‑core System‑on‑Chip (SoC) platforms, driven by the requirements of software‑defined vehicles. This evolution makes it more challenging to assign software components while ensuring both safety and real‑time performance. Here, existing static and dynamic allocation approaches often face difficulties in achieving an optimal balance between determinism, adaptability, and efficiency.



RunSoC delivers a versatile, metrics‑guided framework that incorporates task dependencies and safety criticality, enabling reproducible, performance‑focused scheduling and allocation for next‑generation software‑defined vehicles.



The repository incorporates theoretical background developed through a rapid review of relevant literature, complemented by expert consultations in an automotive industry context. 

The repository is kept anonymous to satisfy the requirement of blind peer reviews for manuscript submission at scientific journals.
Once the peer review is complete, the repository will be updated with researcher-specific data and a reference to the manuscript containing detailed information.



## Core Capabilities



1. **Directed Acyclic Graph (DAG) Construction**

    * Enables users to define custom tasks and their dependencies.
    
    * Automatically builds a DAG to represent the workload.
    
    * Supports both periodic and event-driven task types.
    
    * Provides visualization of task dependencies for validation and analysis.



2. **Task Scheduling**

    * Implements two scheduling policies:
    
      * FCFS (First-Come-First-Served) – optimized for simplicity and low overhead.
    
      * PAS (Priority-Aware Scheduling) – respects task priority levels, suited for safety-critical workloads.
    
    * Integrates both periodic and event-driven semantics in one cohesive scheduling framework.
    
    * Operates with a global event loop that advances system time and evaluates decisions at discrete “decision points.”
    
    * Enforces strict periodicity guard logic to ensure timing integrity of periodic tasks.



3. **Core Allocation and Parallelization**

    * Provides two complementary allocation strategies:
    
      * Static Core Allocation: fixed number of cores assigned at simulation start; deterministic and low overhead.
    
      * Dynamic Core Allocation: adjusts the number of active cores in real time depending on task eligibility; supports adaptability.
    
    * Calculates optimal allocation using metrics like maximum parallelism (Pmax) and minimum required core count (Nmin).
    
    * Ensures efficient resource utilization and analysis of makespan (total completion time).



4. **Simulation and Evaluation Environment**

    * Built as a modular web-based simulation system with:
    
      * Frontend (Next.js/React): interactive interface for input, configuration, and DAG visualization.
    
      * Backend (Python): executes all scheduling, allocation, and simulation logic.
    
    * Nginx deployment enables seamless communication and integrated execution between frontend and backend.



5. **Input/Output and Visualization**

    * User inputs include:
    
      * Number of cores (C)
    
      * Scheduling policy (FCFS or PAS)
    
      * Allocation mode (static or dynamic)
    
      * Task definitions (execution time, priority, dependencies)
    
      * Simulation iterations
    
    * Outputs include:
    
      * Schedule trace (task, start time, finish time, core)
    
      * Gantt chart visualization
    
    * Performance metrics:
    
      * Makespan
    
      * Critical path length (TCP)
    
      * Total work (W)
    
      * Maximum parallelism (Pmax)
    
      * Average core utilization (Cavg)



6. **Data Structures and Simulation Logic**

    * Employs efficient internal representations:
    
      * Task objects (with properties such as ID, execution time, priority, dependencies).
    
      * Ready queue using a custom comparator (based on time or priority).
    
      * Execution log and core pool to track allocation states.
    
    * Event-driven main loop ensures deterministic progression and reproducible simulation.



7. **Analytical and Evaluation Capabilities**

    * Supports comparative studies (e.g., static vs. dynamic allocation, FCFS vs. PAS).
    
    * Provides derived analytical metrics like throughput, latency, and core utilization.
    
    * Enables performance benchmarking with different task structures (long critical path vs. balanced DAG).



8. **Design Principles and Extendability**

    * Integrates dependency- and priority-awareness in scheduling and allocation.
    
    * Offers practical guidelines for selecting allocation/scheduling methods based on measurable metrics.
    
    * Designed for reproducibility, determinism, and scalability in research and real-world SoC evaluations.
    
    * Future-ready for extensions such as:
    
      * Heterogeneous SoC support (different core types)
    
      * Adaptive load balancing
    
      * Enhanced periodicity guards
    
      * Redundancy and fault-tolerance mechanisms

