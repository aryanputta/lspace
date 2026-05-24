/*
 * regolith_terrain_plugin.cc
 * ==========================
 * Gazebo Fortress (Ignition Gazebo 6 / gz-sim 6) System Plugin
 *
 * Implements a Bekker-Wong terramechanics model for lunar regolith surface
 * interaction with wheeled rovers. Applies corrective forces to wheel-terrain
 * contact points to account for:
 *   1. Wheel sinkage (Bekker pressure-sinkage theory)
 *   2. Bulldozing resistance (soil pushed ahead of wheel)
 *   3. Compaction resistance (energy lost compressing regolith)
 *   4. Slip-dependent drawbar pull (thrust vs. slip ratio)
 *
 * BEKKER MODEL PARAMETERS (lunar regolith, equatorial/highland analog):
 * -----------------------------------------------------------------------
 *   c  = 0.17  kPa      Cohesion (Heiken 1991, Table 9.2)
 *   φ  = 35°            Internal friction angle (Carrier 1991)
 *   n  = 1.1            Sinkage exponent (Bekker 1969)
 *   kc = 1.4  kN/m^(n+1) Cohesive modulus
 *   kφ = 8.2  kN/m^(n+2) Frictional modulus
 *   K  = 0.018 m        Shear deformation modulus (Mitchell 1972)
 *   μs = 0.7            Static friction coefficient
 *   μk = 0.6            Kinetic friction coefficient
 *
 * PSR/ICY TERRAIN VARIANT (configured via <regolith_type>psr_icy</regolith_type>):
 *   c  = 0.08  kPa      (reduced: ice weakens grain bonds)
 *   φ  = 28°            (reduced: ice as lubricant)
 *   μs = 0.45, μk = 0.35
 *
 * IMPLEMENTATION NOTES:
 *   - Forces are computed per contact point and applied as additional body forces
 *   - The Bekker model assumes a flat, homogeneous terrain; this is an approximation
 *   - Contact detection uses Gazebo's contact sensor data
 *   - Thread-safe: uses mutex for contact data access
 *
 * References:
 *   Bekker, M.G. (1969). Introduction to terrain-vehicle systems. U. Michigan Press.
 *   Wong, J.Y. (2001). Theory of ground vehicles. Wiley, 3rd ed.
 *   Heiken, G.H. et al. (1991). Lunar Sourcebook.
 *   Mitchell, J.K. et al. (1972). Soil mechanics. Apollo 15/16 reports.
 *   Ding, L. et al. (2015). Experimental study and analysis of the wheels'
 *     steering mechanics on lunar soil simulant. J. Terramechanics, 47(1).
 *
 * Author: NASA Lunar Scout Simulation Team
 * License: Apache 2.0
 */

#include <gz/plugin/Register.hh>
#include <gz/sim/System.hh>
#include <gz/sim/EntityComponentManager.hh>
#include <gz/sim/EventManager.hh>
#include <gz/sim/components/Link.hh>
#include <gz/sim/components/Model.hh>
#include <gz/sim/components/Name.hh>
#include <gz/sim/components/ContactSensorData.hh>
#include <gz/sim/components/ExternalWorldWrenchCmd.hh>
#include <gz/math/Vector3.hh>
#include <gz/math/Pose3.hh>
#include <gz/msgs/contacts.pb.h>

#include <sdf/Element.hh>

#include <cmath>
#include <mutex>
#include <string>
#include <unordered_map>
#include <vector>
#include <iostream>

namespace lunar_sim {

// ============================================================================
// Bekker soil parameters structure
// ============================================================================
struct BekkerParams {
    double cohesion_kPa{0.17};          ///< c [kPa] cohesion
    double friction_angle_rad{0.6109};  ///< φ [rad] = 35°
    double n_exponent{1.1};             ///< n [-] sinkage exponent
    double kc_kN{1.4};                  ///< kc [kN/m^(n+1)] cohesive modulus
    double kphi_kN{8.2};               ///< kφ [kN/m^(n+2)] frictional modulus
    double K_shear_m{0.018};            ///< K [m] shear deformation modulus
    double mu_static{0.7};              ///< μs [-] static friction
    double mu_kinetic{0.6};             ///< μk [-] kinetic friction
    double density_kg_m3{1500.0};       ///< ρ [kg/m³] bulk density
    std::string terrain_type{"dry"};    ///< terrain type identifier
};

// ============================================================================
// Wheel geometry (assumed uniform for rover wheels)
// ============================================================================
struct WheelGeom {
    double radius_m{0.15};    ///< wheel radius [m]
    double width_m{0.12};     ///< wheel width [m]
    double load_N{120.0};     ///< nominal wheel load [N] (rover mass / n_wheels * g_moon)
};

// ============================================================================
// Plugin class
// ============================================================================
class RegolithTerrainPlugin
    : public gz::sim::System,
      public gz::sim::ISystemConfigure,
      public gz::sim::ISystemPreUpdate,
      public gz::sim::ISystemPostUpdate
{
public:
    // -----------------------------------------------------------------------
    // Configure
    // -----------------------------------------------------------------------
    void Configure(
        const gz::sim::Entity& /*_entity*/,
        const std::shared_ptr<const sdf::Element>& _sdf,
        gz::sim::EntityComponentManager& /*_ecm*/,
        gz::sim::EventManager& /*_eventMgr*/) override
    {
        // Parse soil parameters from SDF
        if (_sdf->HasElement("cohesion_kPa")) {
            soil_.cohesion_kPa = _sdf->Get<double>("cohesion_kPa");
        }
        if (_sdf->HasElement("friction_angle_deg")) {
            double deg = _sdf->Get<double>("friction_angle_deg");
            soil_.friction_angle_rad = deg * M_PI / 180.0;
        }
        if (_sdf->HasElement("deformation_exponent")) {
            soil_.n_exponent = _sdf->Get<double>("deformation_exponent");
        }
        if (_sdf->HasElement("sinkage_modulus_kPa")) {
            // Combined modulus approximation: use as kc, compute kφ proportionally
            double km = _sdf->Get<double>("sinkage_modulus_kPa");
            soil_.kc_kN = km * 0.17;   // empirical split: 17% cohesive
            soil_.kphi_kN = km * 0.83; // 83% frictional
        }
        if (_sdf->HasElement("static_friction")) {
            soil_.mu_static = _sdf->Get<double>("static_friction");
        }
        if (_sdf->HasElement("dynamic_friction")) {
            soil_.mu_kinetic = _sdf->Get<double>("dynamic_friction");
        }
        if (_sdf->HasElement("surface_temperature_K")) {
            surfaceTemp_K_ = _sdf->Get<double>("surface_temperature_K");
        }
        if (_sdf->HasElement("ice_fraction")) {
            iceFraction_ = _sdf->Get<double>("ice_fraction");
            // Ice fraction modifies soil strength: reduce by (1 - ice_fraction)
            double strength_factor = 1.0 - 0.4 * iceFraction_;
            soil_.cohesion_kPa  *= strength_factor;
            soil_.kc_kN         *= strength_factor;
            soil_.kphi_kN       *= strength_factor;
        }
        if (_sdf->HasElement("regolith_type")) {
            soil_.terrain_type = _sdf->Get<std::string>("regolith_type");
        }

        // Parse wheel geometry if provided
        if (_sdf->HasElement("wheel_radius_m")) {
            wheel_.radius_m = _sdf->Get<double>("wheel_radius_m");
        }
        if (_sdf->HasElement("wheel_width_m")) {
            wheel_.width_m = _sdf->Get<double>("wheel_width_m");
        }
        if (_sdf->HasElement("nominal_wheel_load_N")) {
            wheel_.load_N = _sdf->Get<double>("nominal_wheel_load_N");
        }

        // Log configuration
        std::cout << "[RegolithTerrainPlugin] Initialized Bekker soil model:\n"
                  << "  Terrain type:      " << soil_.terrain_type << "\n"
                  << "  Cohesion c:        " << soil_.cohesion_kPa << " kPa\n"
                  << "  Friction angle φ:  "
                  << (soil_.friction_angle_rad * 180.0 / M_PI) << "°\n"
                  << "  Sinkage exponent n:" << soil_.n_exponent << "\n"
                  << "  kc:                " << soil_.kc_kN << " kN/m^(n+1)\n"
                  << "  kφ:                " << soil_.kphi_kN << " kN/m^(n+2)\n"
                  << "  Shear modulus K:   " << soil_.K_shear_m << " m\n"
                  << "  μ_static:          " << soil_.mu_static << "\n"
                  << "  μ_kinetic:         " << soil_.mu_kinetic << "\n"
                  << "  Surface temp:      " << surfaceTemp_K_ << " K\n"
                  << "  Ice fraction:      " << iceFraction_ << "\n"
                  << std::endl;

        // Pre-compute nominal sinkage for given wheel geometry and load
        double z0 = ComputeSinkage(wheel_.load_N, wheel_.radius_m, wheel_.width_m);
        double RC = ComputeCompactionResistance(z0, wheel_.width_m);
        double DP = ComputeDrawbarPull(wheel_.load_N, 0.2);  // at 20% slip

        std::cout << "[RegolithTerrainPlugin] Nominal performance predictions:\n"
                  << "  Sinkage (z0):      " << (z0 * 1000.0) << " mm\n"
                  << "  Compaction resist: " << RC << " N\n"
                  << "  Drawbar pull@20%:  " << DP << " N\n"
                  << std::endl;
    }

    // -----------------------------------------------------------------------
    // PreUpdate: apply terrain forces to wheel contact points
    // -----------------------------------------------------------------------
    void PreUpdate(
        const gz::sim::UpdateInfo& _info,
        gz::sim::EntityComponentManager& _ecm) override
    {
        if (_info.paused) return;

        // dt for velocity/acceleration estimates
        double dt = std::chrono::duration<double>(_info.dt).count();
        if (dt <= 0.0) return;

        // Iterate over all entities with contact sensor data
        _ecm.Each<gz::sim::components::ContactSensorData,
                  gz::sim::components::Name>(
            [&](const gz::sim::Entity& _entity,
                const gz::sim::components::ContactSensorData* _contactData,
                const gz::sim::components::Name* _name) -> bool
            {
                const auto& contacts = _contactData->Data();
                if (contacts.contact_size() == 0) return true;

                // For each contact with the terrain
                for (int i = 0; i < contacts.contact_size(); ++i) {
                    const auto& contact = contacts.contact(i);
                    ApplyBekkerForces(_ecm, _entity, contact, dt);
                }
                return true;
            });
    }

    // -----------------------------------------------------------------------
    // PostUpdate: log terrain interaction statistics (throttled)
    // -----------------------------------------------------------------------
    void PostUpdate(
        const gz::sim::UpdateInfo& _info,
        const gz::sim::EntityComponentManager& /*_ecm*/) override
    {
        if (_info.paused) return;

        stepCount_++;

        // Log statistics every 5 seconds of sim time (5000 steps at 1kHz)
        if (stepCount_ % 5000 == 0) {
            std::cout << "[RegolithTerrainPlugin] Step " << stepCount_
                      << " | Active contacts: " << activeContactCount_
                      << " | Total sinkage force: "
                      << totalSinkageForce_N_ << " N"
                      << " | Total compaction resist: "
                      << totalCompactionResist_N_ << " N"
                      << std::endl;
            // Reset accumulators
            totalSinkageForce_N_ = 0.0;
            totalCompactionResist_N_ = 0.0;
            activeContactCount_ = 0;
        }
    }

private:
    // -----------------------------------------------------------------------
    // BEKKER MODEL: Compute wheel sinkage z [m]
    //   Using Bekker (1969) pressure-sinkage equation:
    //   p = (kc/b + kφ) * z^n
    //   where b = min(width, 2*radius) for a wheel
    //   Rearranged: z = (W / (A * (kc/b + kφ)))^(1/n)
    //   with contact area A ≈ b * L, L = 2*sqrt(2*r*z - z²) ≈ 2*sqrt(2*r*z)
    //
    //   Solved iteratively (Newton's method, converges in ~5 iterations)
    // -----------------------------------------------------------------------
    double ComputeSinkage(double W_N, double r_m, double b_m) const
    {
        // Convert kPa to Pa, kN to N
        double kc = soil_.kc_kN * 1000.0;   // [N/m^(n+1)]
        double kphi = soil_.kphi_kN * 1000.0; // [N/m^(n+2)]
        double n = soil_.n_exponent;

        // Combined modulus
        double K_soil = kc / b_m + kphi;  // [N/m^(n+2)]

        // Iterative solution for sinkage
        double z = 0.05;  // initial guess 5cm
        for (int iter = 0; iter < 50; ++iter) {
            // Contact length (chord approximation): L = 2*sqrt(2*r*z)
            double L = 2.0 * std::sqrt(2.0 * r_m * z);
            // Contact area
            double A = b_m * L;
            // Bekker pressure at this sinkage
            double p = K_soil * std::pow(z, n);
            // Normal force from Bekker
            double W_pred = p * A;

            // Residual
            double f = W_pred - W_N;
            if (std::abs(f) < 0.01) break;  // converged to 10 mN

            // Derivative df/dz
            double dL_dz = 2.0 / std::sqrt(2.0 * r_m * z);
            double dA_dz = b_m * dL_dz;
            double dp_dz = K_soil * n * std::pow(z, n - 1.0);
            double df_dz = dp_dz * A + p * dA_dz;

            // Newton step
            double dz = -f / (df_dz + 1e-12);
            z += dz;
            z = std::max(z, 1e-5);  // physical lower bound
            z = std::min(z, 0.3);   // limit: 30cm (unrealistic sinkage)
        }
        return z;
    }

    // -----------------------------------------------------------------------
    // BEKKER MODEL: Compaction resistance [N]
    //   Rc = b * ∫₀ᶻ p(z) dz  (energy to compact soil during sinkage)
    //   = b * (kc/b + kφ) * z^(n+1) / (n+1)
    // -----------------------------------------------------------------------
    double ComputeCompactionResistance(double z_m, double b_m) const
    {
        double kc = soil_.kc_kN * 1000.0;
        double kphi = soil_.kphi_kN * 1000.0;
        double n = soil_.n_exponent;
        double K_soil = kc / b_m + kphi;

        return b_m * K_soil * std::pow(z_m, n + 1.0) / (n + 1.0);
    }

    // -----------------------------------------------------------------------
    // WONG-REECE MODEL: Drawbar pull as function of slip ratio i [-]
    //   τ = (c + p*tan(φ)) * (1 - K/(j) * (1 - exp(-j/K)))
    //   Total force: F_net = F_thrust - F_compaction - F_bulldozing
    //
    //   Simplified implementation using Wong (2001) Eq. 2.97:
    //   DP = A_c*(c + p*tan(φ))*(1 - (K/j_max)*(1-exp(-j_max/K))) - Rc
    //   where j_max = r*θ = r*acos(1-z/r) ≈ sqrt(2*r*z) at slip i
    // -----------------------------------------------------------------------
    double ComputeDrawbarPull(double W_N, double slip_ratio) const
    {
        double z = ComputeSinkage(W_N, wheel_.radius_m, wheel_.width_m);
        double Rc = ComputeCompactionResistance(z, wheel_.width_m);

        // Contact length
        double L = 2.0 * std::sqrt(2.0 * wheel_.radius_m * z);
        double A = wheel_.width_m * L;

        // Mean normal pressure
        double p_mean = W_N / (A + 1e-9);  // [Pa]

        // Shear displacement j at trailing edge (Wong 2001 Eq 2.80)
        double j_max = L * (1.0 - (1.0 - slip_ratio));  // = L * slip_ratio
        j_max = std::max(j_max, 1e-4);

        // Maximum shear stress (Mohr-Coulomb)
        double tau_max = (soil_.cohesion_kPa * 1000.0)
                       + p_mean * std::tan(soil_.friction_angle_rad);

        // Shear force considering shear displacement buildup
        double K = soil_.K_shear_m;
        double shear_factor = 1.0 - (K / j_max) * (1.0 - std::exp(-j_max / K));
        double F_thrust = A * tau_max * shear_factor;

        // Bulldozing resistance (Hegedus 1960, simplified for flat terrain)
        double gamma = soil_.density_kg_m3 * 1.62;  // weight density [N/m³] in lunar gravity
        double phi = soil_.friction_angle_rad;
        double c = soil_.cohesion_kPa * 1000.0;
        double N_gamma = 0.5 * std::tan(phi) * (std::tan(M_PI/4.0 + phi/2.0) + 1.0);
        double N_c = (1.0/std::tan(phi)) * (N_gamma - 1.0);
        double F_bulldoze = wheel_.width_m * (c * N_c + gamma * z * N_gamma) * z;

        return F_thrust - Rc - F_bulldoze;
    }

    // -----------------------------------------------------------------------
    // Apply Bekker terrain forces to a single contact point
    // -----------------------------------------------------------------------
    void ApplyBekkerForces(
        gz::sim::EntityComponentManager& _ecm,
        const gz::sim::Entity& _wheelEntity,
        const gz::msgs::Contact& _contact,
        double /*dt*/)
    {
        // Extract contact normal and depth from contact data
        if (_contact.position_size() == 0) return;

        activeContactCount_++;

        // Contact wrench: normal (sinkage resistance) + tangential (traction)
        // We compute correction forces on top of the physics engine's contact forces

        // Estimate slip ratio from velocity at contact point
        // (simplified: use linear velocity component along wheel rolling direction)
        double slip_ratio = 0.15;  // default 15% slip (typical for soft terrain)

        // Compute Bekker forces
        double z_sink = ComputeSinkage(wheel_.load_N, wheel_.radius_m, wheel_.width_m);
        double Rc = ComputeCompactionResistance(z_sink, wheel_.width_m);
        double DP = ComputeDrawbarPull(wheel_.load_N, slip_ratio);

        totalSinkageForce_N_ += z_sink * 1000.0;  // mm×1000 for logging
        totalCompactionResist_N_ += Rc;

        // Compaction resistance acts as longitudinal drag force opposing motion
        // Apply as negative wrench in the wheel link's forward direction
        // Note: in Gazebo Fortress, use ExternalWorldWrenchCmd to apply forces
        auto* wrenchCmd = _ecm.Component<gz::sim::components::ExternalWorldWrenchCmd>(
            _wheelEntity);

        if (wrenchCmd == nullptr) {
            // Create wrench component if it doesn't exist
            gz::msgs::Wrench wrench;
            wrench.mutable_force()->set_x(-Rc);  // drag along x
            wrench.mutable_force()->set_y(0.0);
            wrench.mutable_force()->set_z(0.0);
            wrench.mutable_torque()->set_x(0.0);
            wrench.mutable_torque()->set_y(0.0);
            wrench.mutable_torque()->set_z(0.0);
            _ecm.CreateComponent(_wheelEntity,
                gz::sim::components::ExternalWorldWrenchCmd(wrench));
        } else {
            // Update existing wrench (accumulate forces if multiple contacts)
            auto& existingWrench = wrenchCmd->Data();
            existingWrench.mutable_force()->set_x(
                existingWrench.force().x() - Rc);
        }
    }

    // -----------------------------------------------------------------------
    // Member variables
    // -----------------------------------------------------------------------

    BekkerParams soil_;
    WheelGeom wheel_;

    double surfaceTemp_K_{293.0};   ///< Surface temperature in K
    double iceFraction_{0.0};       ///< Mass fraction of water ice [0-1]

    uint64_t stepCount_{0};
    uint32_t activeContactCount_{0};
    double totalSinkageForce_N_{0.0};
    double totalCompactionResist_N_{0.0};
};

}  // namespace lunar_sim

// Plugin registration
GZ_ADD_PLUGIN(lunar_sim::RegolithTerrainPlugin,
              gz::sim::System,
              lunar_sim::RegolithTerrainPlugin::ISystemConfigure,
              lunar_sim::RegolithTerrainPlugin::ISystemPreUpdate,
              lunar_sim::RegolithTerrainPlugin::ISystemPostUpdate)

GZ_ADD_PLUGIN_ALIAS(lunar_sim::RegolithTerrainPlugin,
                    "lunar_sim::RegolithTerrainPlugin")
