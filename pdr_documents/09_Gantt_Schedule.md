# LPAS Project Schedule
**Document:** LPAS-SCHED-001 | **Revision:** PDR-A

---

## Program Milestone Timeline

```mermaid
gantt
    title LPAS Mission Development Schedule
    dateFormat  YYYY-MM
    axisFormat  %Y-%m

    section Phase A — Concept
    Mission Concept Review (MCR)          :milestone, m1, 2025-01, 0d
    Trade Studies                         :done,      a1, 2025-01, 3M
    Science Traceability Matrix           :done,      a2, 2025-02, 2M
    System Requirements Review (SRR)     :milestone, m2, 2025-04, 0d
    ConOps Development                    :done,      a3, 2025-03, 3M
    Architecture Trades                   :done,      a4, 2025-04, 2M

    section Phase B — PDR
    Preliminary Design (PDR)             :milestone, m3, 2026-06, 0d
    URDF/CAD Preliminary Models          :active,    b1, 2025-05, 13M
    ROS2 FSW Architecture                :active,    b2, 2025-06, 12M
    AI Model Development Phase 1         :active,    b3, 2025-07, 11M
    Gazebo Simulation Environment         :active,    b4, 2025-08, 10M
    Thermal/Power Analysis               :active,    b5, 2025-09, 9M
    Requirements Traceability            :active,    b6, 2025-10, 8M
    PDR Documentation Package            :active,    b7, 2026-03, 3M

    section Phase C — CDR
    Critical Design Review (CDR)         :milestone, m4, 2027-06, 0d
    Detailed CAD + NX Assemblies         :           c1, 2026-07, 12M
    PCB Design + Layout                  :           c2, 2026-09, 10M
    AI Model Training + Validation       :           c3, 2026-07, 9M
    Software Integration                 :           c4, 2026-10, 8M
    Structural Analysis (FEA)            :           c5, 2026-08, 6M
    Thermal Analysis (TVAC model)        :           c6, 2026-09, 9M
    CDR Documentation Package            :           c7, 2027-03, 3M

    section Phase D — Integration & Test
    Test Readiness Review (TRR)          :milestone, m5, 2028-01, 0d
    Engineering Model (EM) Build         :           d1, 2027-07, 6M
    EM Environmental Testing             :           d2, 2027-10, 4M
    Flight Model (FM) Build              :           d3, 2027-12, 6M
    FM Acceptance Test Procedure         :           d4, 2028-03, 3M
    Launch Readiness Review (LRR)        :milestone, m6, 2028-06, 0d
    Pre-Ship Review                      :milestone, m7, 2028-07, 0d
    Integration with CLPS Lander         :           d5, 2028-07, 2M

    section Phase E — Operations
    Launch                               :milestone, m8, 2028-10, 0d
    Trans-Lunar Cruise (4–5 days)        :           e1, 2028-10, 0.15M
    Lunar Landing                        :milestone, m9, 2028-11, 0d
    Deployment + Checkout                :           e2, 2028-11, 0.25M
    South Pole Survey Phase              :           e3, 2028-11, 2M
    PSR Entry + Science Phase            :           e4, 2029-01, 1.5M
    End of Mission                       :milestone, m10, 2029-03, 0d
```

---

## Key Milestones

| Milestone | Date | Description |
|-----------|------|-------------|
| MCR | Jan 2025 | Mission Concept Review — scope approved |
| SRR | Apr 2025 | System Requirements Review — requirements baselined |
| **PDR** | **Jun 2026** | **Preliminary Design Review — architecture approved** |
| CDR | Jun 2027 | Critical Design Review — design frozen |
| TRR | Jan 2028 | Test Readiness Review — test procedures approved |
| LRR | Jun 2028 | Launch Readiness Review |
| Launch | Oct 2028 | CLPS launch vehicle (Falcon 9 or Vulcan Centaur) |
| Landing | Nov 2028 | Lunar south pole landing |
| EOM | Mar 2029 | End of primary mission (120 sols) |

---

## Level-of-Effort Summary (Person-Months)

| WBS | Task | Phase A | Phase B | Phase C | Phase D | Total |
|-----|------|---------|---------|---------|---------|-------|
| 1.0 | Project Management | 6 | 12 | 12 | 8 | **38** |
| 2.0 | Systems Engineering | 8 | 18 | 15 | 6 | **47** |
| 3.1 | Chassis & Mobility | 4 | 16 | 20 | 12 | **52** |
| 3.2 | Power System | 3 | 12 | 16 | 8 | **39** |
| 3.3 | Thermal Control | 3 | 10 | 14 | 6 | **33** |
| 3.4 | Avionics & FSW | 6 | 24 | 28 | 14 | **72** |
| 3.5 | Communications | 3 | 10 | 12 | 6 | **31** |
| 3.6 | Science Payload | 5 | 14 | 18 | 10 | **47** |
| 4.0 | Ground System | 2 | 8 | 10 | 8 | **28** |
| 5.0 | I&T | 0 | 4 | 8 | 24 | **36** |
| 6.0 | Mission Ops | 0 | 4 | 8 | 16 | **28** |
| | **TOTAL** | **40** | **132** | **161** | **118** | **451 PM** |
