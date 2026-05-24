/*
 * lunar_gravity_plugin.cc
 * =======================
 * Gazebo Fortress (Ignition Gazebo 6 / gz-sim 6) System Plugin
 *
 * Overrides world gravity to lunar surface value (-1.62 m/s² in Z).
 * The value is configurable from the SDF <plugin> element, allowing
 * easy adjustment for other bodies (Mars = -3.72, asteroid scenarios, etc.)
 *
 * SDF usage:
 *   <plugin filename="liblunargravity_plugin.so" name="lunar_gravity_plugin">
 *     <gravity_z>-1.62</gravity_z>   <!-- optional, default -1.62 -->
 *     <gravity_x>0.0</gravity_x>     <!-- optional, default 0.0   -->
 *     <gravity_y>0.0</gravity_y>     <!-- optional, default 0.0   -->
 *   </plugin>
 *
 * Build:
 *   See CMakeLists.txt in this directory.
 *
 * References:
 *   Williams, J.G. et al. (2014). Lunar interior properties from DE430 lunar
 *   orbit solution. J. Geophys. Res. Planets, 119(7).
 *   g_moon = 1.62 m/s² at surface (equatorial), varies ±0.015 m/s² by
 *   location due to mascons. South pole: ~1.625 m/s².
 *
 * Author: NASA Lunar Scout Simulation Team
 * License: Apache 2.0
 */

#include <gz/plugin/Register.hh>
#include <gz/sim/System.hh>
#include <gz/sim/components/Gravity.hh>
#include <gz/sim/components/World.hh>
#include <gz/sim/EntityComponentManager.hh>
#include <gz/sim/EventManager.hh>
#include <gz/math/Vector3.hh>
#include <sdf/Element.hh>

#include <iostream>
#include <string>

namespace lunar_sim {

/// \brief System plugin that sets and maintains lunar gravity.
///
/// The plugin:
///  1. Reads gravity_x/y/z from SDF on Configure()
///  2. Sets the world Gravity component on first PreUpdate()
///  3. Logs the gravity vector on successful application
///  4. Optionally validates on every N-th update (configurable)
class LunarGravityPlugin
    : public gz::sim::System,
      public gz::sim::ISystemConfigure,
      public gz::sim::ISystemPreUpdate
{
public:
    // ---------------------------------------------------------------
    // ISystemConfigure - called once when plugin is loaded
    // ---------------------------------------------------------------
    void Configure(
        const gz::sim::Entity& _entity,
        const std::shared_ptr<const sdf::Element>& _sdf,
        gz::sim::EntityComponentManager& _ecm,
        gz::sim::EventManager& /*_eventMgr*/) override
    {
        this->worldEntity_ = _entity;

        // Parse gravity components from SDF, use lunar defaults if absent
        if (_sdf->HasElement("gravity_z")) {
            this->gravityZ_ = _sdf->Get<double>("gravity_z");
        }
        if (_sdf->HasElement("gravity_x")) {
            this->gravityX_ = _sdf->Get<double>("gravity_x");
        }
        if (_sdf->HasElement("gravity_y")) {
            this->gravityY_ = _sdf->Get<double>("gravity_y");
        }

        // Parse validation interval
        if (_sdf->HasElement("validate_every_n_steps")) {
            this->validateInterval_ = _sdf->Get<uint64_t>("validate_every_n_steps");
        }

        std::cout << "[LunarGravityPlugin] Configured. Target gravity vector: ["
                  << this->gravityX_ << ", "
                  << this->gravityY_ << ", "
                  << this->gravityZ_ << "] m/s²" << std::endl;

        // Validate reasonable lunar range (warn if far outside lunar value)
        double gMag = std::abs(this->gravityZ_);
        if (gMag < 0.5 || gMag > 10.0) {
            std::cerr << "[LunarGravityPlugin] WARNING: |gravity_z| = " << gMag
                      << " m/s² is outside expected planetary range [0.5, 10.0]. "
                      << "Lunar south pole: 1.625 m/s². Proceeding anyway." << std::endl;
        }
    }

    // ---------------------------------------------------------------
    // ISystemPreUpdate - called every simulation step
    // ---------------------------------------------------------------
    void PreUpdate(
        const gz::sim::UpdateInfo& _info,
        gz::sim::EntityComponentManager& _ecm) override
    {
        // Apply gravity on first update only (unless validation is enabled)
        if (!this->gravityApplied_) {
            ApplyGravity(_ecm);
            this->gravityApplied_ = true;
        }

        // Periodic validation: re-apply and check for drift or override
        if (this->validateInterval_ > 0 &&
            (_info.iterations % this->validateInterval_) == 0)
        {
            ValidateAndReapply(_ecm);
        }

        this->stepCount_++;
    }

private:
    // ---------------------------------------------------------------
    // Set the Gravity component on the world entity
    // ---------------------------------------------------------------
    void ApplyGravity(gz::sim::EntityComponentManager& _ecm)
    {
        gz::math::Vector3d gravityVec(
            this->gravityX_,
            this->gravityY_,
            this->gravityZ_
        );

        // Check if Gravity component already exists (set by physics engine)
        auto* gravComp = _ecm.Component<gz::sim::components::Gravity>(
            this->worldEntity_);

        if (gravComp != nullptr) {
            // Component exists: update its value
            gz::math::Vector3d prev = gravComp->Data();
            gravComp->SetData(gravityVec,
                [](const gz::math::Vector3d&, const gz::math::Vector3d&) {
                    return false;  // always mark dirty
                });
            _ecm.SetChanged(
                this->worldEntity_,
                gz::sim::components::Gravity::typeId,
                gz::sim::ComponentState::PeriodicChange);

            std::cout << "[LunarGravityPlugin] Gravity component updated: "
                      << prev << " → " << gravityVec << " m/s²" << std::endl;
        } else {
            // Component doesn't exist: create it
            _ecm.CreateComponent(this->worldEntity_,
                gz::sim::components::Gravity(gravityVec));
            std::cout << "[LunarGravityPlugin] Gravity component created: "
                      << gravityVec << " m/s²" << std::endl;
        }

        std::cout << "[LunarGravityPlugin] ✓ Lunar gravity applied. "
                  << "|g| = " << gravityVec.Length() << " m/s² "
                  << "(Moon surface reference: 1.62 m/s²)" << std::endl;
    }

    // ---------------------------------------------------------------
    // Periodic check to ensure gravity hasn't been reset by another plugin
    // ---------------------------------------------------------------
    void ValidateAndReapply(gz::sim::EntityComponentManager& _ecm)
    {
        auto* gravComp = _ecm.Component<gz::sim::components::Gravity>(
            this->worldEntity_);

        if (gravComp == nullptr) {
            std::cerr << "[LunarGravityPlugin] WARNING: Gravity component missing "
                      << "at step " << this->stepCount_
                      << ". Re-creating." << std::endl;
            ApplyGravity(_ecm);
            return;
        }

        gz::math::Vector3d current = gravComp->Data();
        gz::math::Vector3d target(this->gravityX_, this->gravityY_, this->gravityZ_);

        if ((current - target).Length() > 1e-6) {
            std::cerr << "[LunarGravityPlugin] WARNING: Gravity drift detected at step "
                      << this->stepCount_ << ". "
                      << "Current: " << current
                      << ", Target: " << target
                      << ". Re-applying." << std::endl;
            ApplyGravity(_ecm);
        }
    }

    // ---------------------------------------------------------------
    // Member variables
    // ---------------------------------------------------------------

    /// World entity handle
    gz::sim::Entity worldEntity_{gz::sim::kNullEntity};

    /// Gravity components (m/s²)
    /// Default: lunar south pole value
    /// (GRAIL mission measurement at 89.5°S: 1.6247 m/s²)
    double gravityX_{0.0};
    double gravityY_{0.0};
    double gravityZ_{-1.62};

    /// Whether gravity has been applied in the first PreUpdate
    bool gravityApplied_{false};

    /// Step counter
    uint64_t stepCount_{0};

    /// Validate gravity every N steps (0 = disable)
    uint64_t validateInterval_{0};
};

}  // namespace lunar_sim

// Register as a Gazebo Fortress System plugin
GZ_ADD_PLUGIN(lunar_sim::LunarGravityPlugin,
              gz::sim::System,
              lunar_sim::LunarGravityPlugin::ISystemConfigure,
              lunar_sim::LunarGravityPlugin::ISystemPreUpdate)

GZ_ADD_PLUGIN_ALIAS(lunar_sim::LunarGravityPlugin,
                    "lunar_sim::LunarGravityPlugin")
