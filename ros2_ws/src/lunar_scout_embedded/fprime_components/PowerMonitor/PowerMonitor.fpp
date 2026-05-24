# PowerMonitor.fpp — F Prime power management component
module Lpas {

  @ LPAS power monitor — solar, battery, load management
  active component PowerMonitor {

    # ── Inputs ───────────────────────────────────────────────────────────────
    @ Solar irradiance measurement (W/m²)
    async input port solarIrradiance: Fw.SensorF32

    @ Battery voltage (V)
    async input port batteryVoltage: Fw.SensorF32

    @ Battery current (A, + = charging)
    async input port batteryCurrent: Fw.SensorF32

    @ Battery temperature (°C)
    async input port batteryTemp: Fw.SensorF32

    @ Total system load (W)
    async input port systemLoad: Fw.SensorF32

    @ Load shed request
    async input port loadShedRequest: Lpas.LoadShedCmd

    # ── Outputs ──────────────────────────────────────────────────────────────
    @ Power mode command to all loads
    output port powerModeCmd: Lpas.PowerModeMsg

    @ Battery state report
    output port batteryState: Lpas.BatteryStateMsg

    @ Power fault alert
    output port powerFault: Fw.FaultReport

    # ── Parameters ────────────────────────────────────────────────────────────
    param batteryCapacityWh:   F32 default 150.0
    param lowSocThreshold:     F32 default 0.20
    param criticalSocThreshold: F32 default 0.10
    param solarArrayArea:      F32 default 1.2
    param cellEfficiency:      F32 default 0.295

    # ── Telemetry ─────────────────────────────────────────────────────────────
    telemetry soc:              F32 format "{.1f}"
    telemetry batteryVoltage:   F32 format "{.2f} V"
    telemetry batteryCurrent:   F32 format "{.2f} A"
    telemetry solarPower:       F32 format "{.1f} W"
    telemetry systemLoadW:      F32 format "{.1f} W"
    telemetry netPower:         F32 format "{.1f} W"
    telemetry remainingWh:      F32 format "{.1f} Wh"
    telemetry timeToEmptyH:     F32 format "{.2f} h"
    telemetry powerMode:        U8  format "{}"
    telemetry heaterPowerW:     F32 format "{.1f} W"

    # ── Events ────────────────────────────────────────────────────────────────
    event LowSoc(soc: F32) \
      severity warning high \
      format "Battery SOC low: {.1f}%"

    event CriticalSoc(soc: F32) \
      severity fatal \
      format "Battery SOC critical: {.1f}% — entering survival mode"

    event LoadShed(subsystem: string size 32, load_w: F32) \
      severity warning high \
      format "Load shed: {} ({.1f} W)"

    event SolarChargingStarted(power_w: F32) \
      severity activity low \
      format "Solar charging started: {.1f} W"

    event EclipseDetected \
      severity warning high \
      format "Solar power < 1W — eclipse or PSR detected"

    event PowerModeChanged(from: U8, to: U8) \
      severity activity low \
      format "Power mode: {} → {}"

    # ── Commands ──────────────────────────────────────────────────────────────
    async command FORCE_POWER_MODE(mode: U8)
    async command ENABLE_LOAD(subsystem: string size 32)
    async command DISABLE_LOAD(subsystem: string size 32)
    async command RESET_ENERGY_COUNTER()
  }

}
