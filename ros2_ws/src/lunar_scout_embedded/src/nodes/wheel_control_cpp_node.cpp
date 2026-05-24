// wheel_control_cpp_node.cpp — real-time C++ wheel control ROS2 lifecycle node
#include <chrono>
#include <memory>
#include <string>
#include <array>

#include "rclcpp/rclcpp.hpp"
#include "rclcpp_lifecycle/lifecycle_node.hpp"
#include "geometry_msgs/msg/twist.hpp"
#include "nav_msgs/msg/odometry.hpp"
#include "std_msgs/msg/float64_multi_array.hpp"
#include "sensor_msgs/msg/joint_state.hpp"

#include "lpas/rocker_bogie_kinematics.hpp"
#include "lpas/bekker_soil_model.hpp"

using namespace std::chrono_literals;
using rclcpp_lifecycle::LifecycleNode;
using CallbackReturn = rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn;

class WheelControlCppNode : public LifecycleNode {
public:
    WheelControlCppNode() : LifecycleNode("wheel_control_cpp_node") {
        declare_parameter("control_hz",   20.0);
        declare_parameter("odom_hz",      50.0);
        declare_parameter("slip_limit",   0.35);
        declare_parameter("max_speed_mps", 0.5);
    }

    // ── Lifecycle ─────────────────────────────────────────────────────────────
    CallbackReturn on_configure(const rclcpp_lifecycle::State&) override {
        RCLCPP_INFO(get_logger(), "Configuring wheel control (C++) node");

        // Publishers
        pub_wheel_vel_ = create_publisher<std_msgs::msg::Float64MultiArray>(
            "/wheel_velocities", rclcpp::QoS(5).best_effort());
        pub_odom_ = create_publisher<nav_msgs::msg::Odometry>(
            "/wheel_control/odometry", rclcpp::QoS(10).reliable());
        pub_slip_ = create_publisher<std_msgs::msg::Float64MultiArray>(
            "/wheel_control/slip_status", rclcpp::QoS(5).best_effort());
        pub_joint_ = create_publisher<sensor_msgs::msg::JointState>(
            "/joint_states", rclcpp::QoS(5).best_effort());

        // Subscriptions
        sub_cmd_vel_ = create_subscription<geometry_msgs::msg::Twist>(
            "/cmd_vel", rclcpp::QoS(10).reliable(),
            [this](const geometry_msgs::msg::Twist::SharedPtr msg) {
                cmd_.linear_x  = msg->linear.x;
                cmd_.angular_z = msg->angular.z;
                last_cmd_time_ = now();
            });

        sub_encoders_ = create_subscription<std_msgs::msg::Float64MultiArray>(
            "/wheel_encoders", rclcpp::QoS(5).best_effort(),
            [this](const std_msgs::msg::Float64MultiArray::SharedPtr msg) {
                if (msg->data.size() >= 6) {
                    for (int i = 0; i < 6; ++i) wheel_omega_[i] = msg->data[i];
                }
            });

        sub_slip_ = create_subscription<std_msgs::msg::Float64MultiArray>(
            "/wheel_slip_predictions", rclcpp::QoS(5).best_effort(),
            [this](const std_msgs::msg::Float64MultiArray::SharedPtr msg) {
                if (msg->data.size() >= 6) {
                    for (int i = 0; i < 6; ++i) slip_pred_[i] = msg->data[i];
                }
            });

        return CallbackReturn::SUCCESS;
    }

    CallbackReturn on_activate(const rclcpp_lifecycle::State&) override {
        RCLCPP_INFO(get_logger(), "Activating wheel control (C++) node");

        double ctrl_hz = get_parameter("control_hz").as_double();
        double odom_hz = get_parameter("odom_hz").as_double();

        timer_control_ = create_wall_timer(
            std::chrono::duration<double>(1.0 / ctrl_hz),
            [this]() { control_loop(); });

        timer_odom_ = create_wall_timer(
            std::chrono::duration<double>(1.0 / odom_hz),
            [this]() { publish_odometry(); });

        last_cmd_time_  = now();
        last_odom_time_ = now();

        // Pre-compute Bekker sinkage at nominal load
        lpas::RegolithParams soil{};
        lpas::WheelParams    wheel{};
        sinkage_ = lpas::compute_sinkage(soil, wheel);

        RCLCPP_INFO(get_logger(),
            "Bekker sinkage (nominal): %.1f mm, contact area %.1f cm²",
            sinkage_.sinkage_m * 1000.0,
            sinkage_.contact_area_m2 * 1e4);

        return CallbackReturn::SUCCESS;
    }

    CallbackReturn on_deactivate(const rclcpp_lifecycle::State&) override {
        timer_control_->cancel();
        timer_odom_->cancel();
        send_zero_velocities();
        return CallbackReturn::SUCCESS;
    }

    CallbackReturn on_cleanup(const rclcpp_lifecycle::State&) override {
        timer_control_.reset();
        timer_odom_.reset();
        return CallbackReturn::SUCCESS;
    }

    CallbackReturn on_shutdown(const rclcpp_lifecycle::State&) override {
        send_zero_velocities();
        return CallbackReturn::SUCCESS;
    }

private:
    // ── Control loop (20 Hz) ──────────────────────────────────────────────────
    void control_loop() {
        // Timeout: zero velocity if no cmd_vel for 1 second
        auto elapsed = (now() - last_cmd_time_).seconds();
        if (elapsed > 1.0) {
            cmd_ = {0.0, 0.0};
        }

        // Smooth velocity via rate limiting
        constexpr double dt        = 1.0 / 20.0;
        constexpr double lin_rate  = 0.3 * dt;   // 0.3 m/s² accel
        constexpr double ang_rate  = 0.2 * dt;

        smooth_cmd_.linear_x  = rate_limit(smooth_cmd_.linear_x,  cmd_.linear_x,  lin_rate);
        smooth_cmd_.angular_z = rate_limit(smooth_cmd_.angular_z, cmd_.angular_z, ang_rate);

        auto velocities = lpas::compute_wheel_velocities(smooth_cmd_, geo_);

        // Apply traction control
        double slip_limit = get_parameter("slip_limit").as_double();
        velocities = lpas::traction_control(velocities, slip_pred_, slip_limit);

        // Publish
        send_wheel_velocities(velocities);
    }

    static double rate_limit(double curr, double target, double max_delta) noexcept {
        double delta = target - curr;
        if (delta >  max_delta) delta =  max_delta;
        if (delta < -max_delta) delta = -max_delta;
        return curr + delta;
    }

    void send_wheel_velocities(const lpas::WheelVelocities& v) {
        std_msgs::msg::Float64MultiArray msg;
        msg.data = std::vector<double>(v.begin(), v.end());
        pub_wheel_vel_->publish(msg);

        // Slip status
        std_msgs::msg::Float64MultiArray slip_msg;
        slip_msg.data = std::vector<double>(slip_pred_.begin(), slip_pred_.end());
        pub_slip_->publish(slip_msg);

        // Joint states for RViz
        sensor_msgs::msg::JointState js;
        js.header.stamp = now();
        static const std::vector<std::string> jnames = {
            "wheel_fl_joint","wheel_ml_joint","wheel_rl_joint",
            "wheel_fr_joint","wheel_mr_joint","wheel_rr_joint"
        };
        js.name = jnames;
        js.velocity = std::vector<double>(v.begin(), v.end());
        pub_joint_->publish(js);
    }

    void send_zero_velocities() {
        lpas::WheelVelocities zeros{};
        zeros.fill(0.0);
        send_wheel_velocities(zeros);
    }

    // ── Odometry (50 Hz) ──────────────────────────────────────────────────────
    void publish_odometry() {
        auto t_now = now();
        double dt  = (t_now - last_odom_time_).seconds();
        last_odom_time_ = t_now;

        // Wheel-averaged body speeds (slip-affected)
        lpas::TwistCmd body = lpas::wheel_velocities_to_twist(wheel_omega_, geo_);

        // Integrate pose
        x_   += body.linear_x * std::cos(yaw_) * dt;
        y_   += body.linear_x * std::sin(yaw_) * dt;
        yaw_ += body.angular_z * dt;

        nav_msgs::msg::Odometry odom;
        odom.header.stamp    = t_now;
        odom.header.frame_id = "odom";
        odom.child_frame_id  = "base_footprint";

        odom.pose.pose.position.x = x_;
        odom.pose.pose.position.y = y_;
        odom.pose.pose.position.z = 0.0;

        // Yaw quaternion
        odom.pose.pose.orientation.w = std::cos(yaw_ / 2.0);
        odom.pose.pose.orientation.z = std::sin(yaw_ / 2.0);

        odom.twist.twist.linear.x  = body.linear_x;
        odom.twist.twist.angular.z = body.angular_z;

        // Pose covariance (diagonal, dead-reckoning on regolith degrades)
        odom.pose.covariance[0]  = 0.01;
        odom.pose.covariance[7]  = 0.01;
        odom.pose.covariance[35] = 0.005;

        pub_odom_->publish(odom);
    }

    // ── Members ───────────────────────────────────────────────────────────────
    rclcpp_lifecycle::LifecyclePublisher<std_msgs::msg::Float64MultiArray>::SharedPtr pub_wheel_vel_;
    rclcpp_lifecycle::LifecyclePublisher<nav_msgs::msg::Odometry>::SharedPtr          pub_odom_;
    rclcpp_lifecycle::LifecyclePublisher<std_msgs::msg::Float64MultiArray>::SharedPtr pub_slip_;
    rclcpp_lifecycle::LifecyclePublisher<sensor_msgs::msg::JointState>::SharedPtr     pub_joint_;

    rclcpp::Subscription<geometry_msgs::msg::Twist>::SharedPtr           sub_cmd_vel_;
    rclcpp::Subscription<std_msgs::msg::Float64MultiArray>::SharedPtr    sub_encoders_;
    rclcpp::Subscription<std_msgs::msg::Float64MultiArray>::SharedPtr    sub_slip_;

    rclcpp::TimerBase::SharedPtr timer_control_;
    rclcpp::TimerBase::SharedPtr timer_odom_;

    lpas::RoverGeometry  geo_{};
    lpas::TwistCmd       cmd_{0.0, 0.0};
    lpas::TwistCmd       smooth_cmd_{0.0, 0.0};
    lpas::WheelVelocities wheel_omega_{};
    std::array<double,6>  slip_pred_{};
    lpas::SinkageResult   sinkage_{};

    // Odometry state
    double x_{0.0}, y_{0.0}, yaw_{0.0};
    rclcpp::Time last_cmd_time_;
    rclcpp::Time last_odom_time_;
};

int main(int argc, char* argv[]) {
    rclcpp::init(argc, argv);
    auto node = std::make_shared<WheelControlCppNode>();
    rclcpp::spin(node->get_node_base_interface());
    rclcpp::shutdown();
    return 0;
}
