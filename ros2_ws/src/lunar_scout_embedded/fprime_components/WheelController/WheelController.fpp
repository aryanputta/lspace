# WheelController.fpp — F Prime component definition
# Inspired by JPL F Prime flight software framework

module Lpas {

  @ LPAS wheel controller component — manages 6-wheel rocker-bogie drive
  active component WheelController {

    # ── Input ports ─────────────────────────────────────────────────────────
    @ Velocity command from autonomy manager
    async input port cmdVel: Fw.CmdVel

    @ Wheel encoder readings (6 wheels, rad/s)
    async input port encoderData: Lpas.WheelEncoderArray

    @ Slip ratio predictions from AI model (6 values, 0–1)
    async input port slipPredictions: Lpas.SlipRatioArray

    @ Traction control enable/disable
    sync input port setTractionControl: Fw.EnableDisable

    # ── Output ports ────────────────────────────────────────────────────────
    @ Motor velocity commands (6 wheels, rad/s)
    output port motorCommands: Lpas.MotorCommandArray

    @ Wheel odometry output
    output port odometry: Lpas.WheelOdometry

    @ Slip status (per-wheel)
    output port slipStatus: Lpas.SlipRatioArray

    @ Fault report
    output port faultOut: Fw.FaultReport

    # ── Internal parameters ──────────────────────────────────────────────────
    @ Maximum traverse speed (m/s)
    param maxSpeedMps: F32 default 0.5

    @ Maximum angular rate (rad/s)
    param maxAngularRatePads: F32 default 0.3

    @ Slip limit for traction control
    param slipLimit: F32 default 0.35

    @ Traction control enabled
    param tractionEnabled: bool default true

    # ── Telemetry ────────────────────────────────────────────────────────────
    telemetry wheelVel_FL: F32 format "{} rad/s"
    telemetry wheelVel_ML: F32 format "{} rad/s"
    telemetry wheelVel_RL: F32 format "{} rad/s"
    telemetry wheelVel_FR: F32 format "{} rad/s"
    telemetry wheelVel_MR: F32 format "{} rad/s"
    telemetry wheelVel_RR: F32 format "{} rad/s"
    telemetry slipRatio_max: F32 format "{}"
    telemetry tractionCorrectionActive: bool

    # ── Events ───────────────────────────────────────────────────────────────
    event WheelSpeedLimit(wheel: U8, commanded: F32, limited: F32) \
      severity warning low \
      format "Wheel {} speed limited from {} to {} rad/s"

    event TractionControl(wheel: U8, slip: F32, scale: F32) \
      severity activity low \
      format "Traction control: wheel {} slip={} scale={}"

    event CommandTimeout \
      severity warning high \
      format "cmd_vel timeout — zeroing wheel velocities"

    event SinkageEstimate(sinkage_mm: F32, contact_area_cm2: F32) \
      severity activity low \
      format "Bekker sinkage: {} mm, contact area {} cm²"

    # ── Commands ─────────────────────────────────────────────────────────────
    async command ENABLE_TRACTION_CONTROL()
    async command DISABLE_TRACTION_CONTROL()
    async command SET_SLIP_LIMIT(limit: F32)
    async command EMERGENCY_STOP()
  }

}
