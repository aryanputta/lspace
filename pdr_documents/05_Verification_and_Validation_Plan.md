# LPAS Verification and Validation Plan
**Document:** LPAS-VVP-001 | **Revision:** PDR-A

Verification methods: **A** = Analysis, **I** = Inspection, **T** = Test, **D** = Demonstration

---

## Verification Matrix (Selected Requirements)

| Req ID | Requirement Statement | Method | Test Description | Success Criterion |
|--------|----------------------|--------|-----------------|-------------------|
| SR-001 | Rover total mass < 250 kg | A + I | Mass properties from CBE + margin analysis; physical weigh at ATP | CBE ≤ 200 kg; MEV ≤ 230 kg |
| SR-002 | Traverse distance > 10 km cumulative | A + D | Gazebo simulation + field demonstration on lunar analog terrain | 10 km logged in simulation; 1 km demonstrated on analog |
| SR-003 | Max slope capability 25° | T + D | TVAC slope table test; regolith simulant test facility (Goddard or JPL) | Successful traverse of 25° slope, slip < 0.4 |
| SR-004 | Ground clearance > 250 mm at nominal sinkage | A + T | Bekker soil model analysis + physical sinkage test in regolith simulant | Clearance ≥ 250 mm measured |
| SR-005 | Solar array output > 150 W (optimal pointing) | T + A | Thermal vacuum solar simulation; I-V curve measurement | P_max > 150 W at AMO equivalent irradiance |
| SR-006 | Battery capacity > 100 Wh usable | T | Cell-level characterization; pack-level discharge test at -10°C | Usable capacity ≥ 120 Wh at -10°C |
| SR-007 | Eclipse survival > 2 hours | T + A | Battery run-down test with survival load profile (52W); thermal model correlation | Voltage ≥ 25.6V (10% SOC) after 2 hours |
| SR-008 | Electronics survival -40°C to +70°C | T | TVAC thermal cycling, 6 cycles -40/+70°C | All electronics functional after cycling |
| SR-009 | Battery operating range -10°C to +40°C | T | Battery thermal chamber tests | Capacity > 80% nominal across range |
| SR-010 | UHF link margin > 3 dB at 5 km | A + T | Link budget analysis + RF range test in EMI chamber | Measured margin ≥ 3 dB |
| SR-011 | Ka-band link margin > 3 dB at 384,400 km | A | Link budget with verified hardware parameters | Analysis shows ≥ 3 dB |
| SR-012 | Autonomous operation > 8 hours | D + A | 8-hour autonomous simulation run without ground uplink | Nominal traverse of > 500m, no faults |
| SR-013 | Navigation accuracy < 3 m after 500 m traverse | T + D | SLAM accuracy vs. ground truth on testbed | RMSE < 3m at 500m without GPS |
| SR-014 | Hazard detection latency < 100 ms | T | Timed inference benchmark on Jetson AGX Orin with test images | P95 latency < 100 ms |
| SR-015 | Hazard detection mAP@0.5 > 0.85 | T | Validation dataset (500 labeled lunar terrain images) | mAP@0.5 ≥ 0.85 |
| SR-016 | FDIR fault response < 200 ms | T | Injected fault scenarios; measure response latency | Isolation + recovery command < 200 ms |
| SR-017 | Drill depth > 0.5 m | T | Mechanical drill test in regolith simulant | 50 cm depth achieved in < 60 min |
| SR-018 | WEH detection threshold < 1 wt% | A + T | Spectrometer calibration with known H₂O samples | Detect 0.5 wt% H₂O at 3σ confidence |
| SR-019 | Software radiation tolerance > 30 krad(Si) | A + I | Analysis of selected processor; review of TID spec | Processor TID spec ≥ 30 krad |
| SR-020 | System reliability MTBF > 2000 h | A | Parts-level MTBF analysis per MIL-HDBK-217 | MTBF > 2000 h at mission operating conditions |

---

## Environmental Test Matrix

| Test | Applicable Subsystems | Facility | Standard |
|------|----------------------|----------|----------|
| Vibration (random, sine) | All | GSFC or JPL vibration lab | GEVS-7000A |
| Thermal vacuum cycling | Electronics, battery, cameras | 6m TVAC chamber | NASA-STD-7001 |
| Shock | Deployment mechanisms | Drop test facility | MIL-STD-810G |
| EMI/EMC | All RF systems | Shielded anechoic chamber | MIL-STD-461G |
| Dust / regolith | Wheel assembly, solar array | Regolith simulant chamber (JSC-1A) | ASTM standards |
| Static load | Chassis, wheel mounts | Structural test frame | ECSS-E-ST-32 |
| Radiation | Flight computer, cameras | Proton/gamma irradiation facility | MIL-STD-883 |
| Thermal cycling (non-vacuum) | Harness, connectors | Thermal chamber | MIL-STD-810G |

---

## Software V&V Approach

### Unit Tests
- Coverage target: > 85% branch coverage for all safety-critical modules
- Framework: pytest (Python), Google Test (C++)
- CI: automated on every commit

### Integration Tests
- ROS2 launch-based integration tests
- Hardware-in-the-loop: Jetson AGX Orin running ONNX models with simulated sensor data
- Fault injection testing: watchdog timeouts, sensor failures, power events

### System-Level Validation
- Full mission simulation in Gazebo: 8-hour autonomous run
- NVIDIA Isaac Sim: high-fidelity physics validation
- Field testing: lunar analog terrain at Pu'u Poli'ahu (Mauna Kea) or Lunar Analogue Test Facility

### Acceptance Test Procedure (ATP) Key Gates
1. Mass properties verification
2. Power system characterization
3. Mobility qualification (slope + sinkage)
4. Communications RF verification
5. FDIR functional test (all fault scenarios)
6. Full autonomy demonstration (1 km traverse)
7. Science payload function test
