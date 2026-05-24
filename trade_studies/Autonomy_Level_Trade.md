# LPAS Autonomy Architecture Trade Study
**Document:** LPAS-TRADE-AUTO-001 | **Revision:** PDR-A | **Date:** 2026-05-24

---

## 1. Communication Environment

| Parameter | Value | Impact |
|-----------|-------|--------|
| Earth-Moon one-way light time | 1.28 s | Round-trip cmd latency: 2.56 s min |
| Effective cmd round-trip (DSN scheduling) | 30–120 min | Human-in-loop impossible for real-time ops |
| LRO UHF contact windows | 2× per Earth day, ~8 min each | 16 min/day total uplink window |
| PSR blackout (no LRO visibility) | Up to 72 hours | Rover must operate fully autonomous |
| Extended eclipse ops | Up to 14 days (edge case) | Requirements: MR-009 |

---

## 2. Autonomy Levels Considered

| Level | Name | Description |
|-------|------|-------------|
| AL1 | Ground-in-Loop | Execute each movement command from Earth |
| **AL2** | **Supervised Autonomy** | **Execute mission scripts; stop on anomaly** |
| **AL3** | **Full Autonomy** | **Self-directed navigation with AI models** |

---

## 3. Trade Analysis

### AL1 — Ground-in-Loop
- **Throughput:** ~0.2 m/cmd × 10 cmd/pass × 2 passes/day = **4 m/day max**
- **Requirement:** 50 m/day minimum traverse — AL1 fails by 12× margin
- **PSR capability:** None — comms blackout in PSR
- **Verdict: Infeasible**

### AL2 — Supervised Autonomy
- **Throughput:** 200–500 m/day with scripted traverse
- **Hazard response:** Auto-stop on slip > 0.4 or hazard detect
- **PSR capability:** Pre-planned PSR entry with abort triggers
- **Comm dependency:** Uplink mission script 1×/day; no real-time supervision
- **Verdict: Sufficient for nominal surface traverse**

### AL3 — Full Autonomy
- **Throughput:** 100–1000 m/day (goal-directed navigation)
- **PSR capability:** Required — AI models guide path inside PSR
- **Comm dependency:** None required during ops
- **Risk:** Higher computational cost; AI model uncertainty in novel terrain
- **Verdict: Required for PSR interior; AL3 triggered only inside PSR boundary**

---

## 4. Selected Architecture

**Decision: AL2 for nominal surface traverse + AL3 inside PSR**

```
Mode                  Autonomy Level  Description
──────────────────────────────────────────────────
Standby               AL1 (idle)      Waiting for uplink
Surface traverse      AL2             Execute mission script
PSR approach          AL2 + AL3       Semi-autonomous, increasing AI reliance
PSR interior          AL3             Full AI-guided navigation
Safe mode             AL1             Minimum function, await ground contact
```

---

## 5. AI Models Required for AL3

| Model | Input | Output | Latency (TRT) | Purpose |
|-------|-------|--------|---------------|---------|
| Terrain Segmentation | RGB 640×480 | 8-class mask | 18 ms | Path planning |
| Hazard Detection | RGB 640×480 | Bounding boxes | 25 ms | Stop trigger |
| Slip Prediction | IMU + wheel enc | Per-wheel slip ratio | 8 ms | Traction control |
| Traversability BEV | LiDAR 3D | Cost map | 35 ms | Nav2 local planner |

Combined inference cycle: ~86 ms → 11.6 Hz → sufficient for 0.2 m/s PSR speed with 0.5s reaction time.

---

## 6. Onboard Compute

| Component | Spec | Power |
|-----------|------|-------|
| Jetson AGX Orin | 275 TOPS INT8, 2048-core Ampere GPU | 30W max |
| RAM | 32 GB LPDDR5 | (included in 30W) |
| NVMe Storage | 64 GB (4K science + FSW) | 3W |
| Operating mode | TensorRT INT8, 10W AI budget | 10W |
| Safety mode | CPU-only (ARM Cortex-A78AE) | 8W |

TensorRT optimization:
- Terrain seg: 120 ms (PyTorch) → 18 ms (TRT INT8)
- Hazard det: 200 ms (PyTorch) → 25 ms (TRT INT8)
- ONNX opset 17, dynamic batch axis

---

## 7. Fault Handling in AL3

| Fault | Trigger | Response |
|-------|---------|---------|
| AI inference timeout > 500ms | Watchdog | Halt, safe mode, alert |
| Slip ratio > 0.6 on any wheel | Slip prediction | Immediate stop, back up 0.5m |
| Battery SOC < 30% | Power monitor | Exit PSR, return to illuminated terrain |
| Hazard detected < 1.5m | HazCam | Emergency stop |
| Thermal limit exceeded | ThermalMonitor | Reduce power, enter safe mode |
| LiDAR data gap > 2s | SLAM toolbox | Hold position, switch to camera-only |

---

## 8. Verification Approach

| Requirement | Method |
|-------------|--------|
| AL3 navigation in simulated PSR | Gazebo Fortress + Isaac Sim |
| AI model accuracy (terrain seg mIoU > 0.72) | Benchmark on LROC NAC dataset |
| Hazard detection recall > 0.95 at 3m | Synthetic + field test |
| Slip prediction error < 0.05 | Hardware-in-loop with regolith testbed |
| End-to-end PSR entry 1.5h demo | JPL Mars Yard analog test (CDR) |
