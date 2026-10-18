/**
 * 5-DOF Robot Arm Kinematics & Motion Engine
 * Handles 5 Joint Forward Kinematics (FK), 3D Inverse Kinematics (IK),
 * Servo Calibration Trims, and Motion Routines.
 */

class ArmKinematics {
    constructor() {
        // Robot Arm Dimensions (in mm)
        this.BASE_HEIGHT  = 80;   // Distance from ground to shoulder pivot
        this.SHOULDER_LEN = 110;  // Upper arm link
        this.ELBOW_LEN    = 120;  // Forearm link
        this.WRIST_LEN    = 70;   // Wrist link
        this.GRIPPER_LEN  = 50;   // End-effector claw length

        // 5 Servo Calibration Trim Angles (in degrees)
        this.calibrationTrims = {
            j1_base: 0,
            j2_shoulder: 0,
            j3_elbow: 0,
            j4_wrist: 0,
            j5_gripper: 0
        };

        // Current Joint Angles (degrees)
        this.jointAngles = {
            j1_base: 0,
            j2_shoulder: 30,
            j3_elbow: 45,
            j4_wrist: 0,
            j5_gripper: 50
        };

        this.activePose = 'Home / Rest';
    }

    /**
     * Solves Forward Kinematics (FK) for 5-DOF Arm
     * Returns 3D positions of all joints & end-effector
     */
    computeForwardKinematics(jointAngles) {
        const trims = this.calibrationTrims;

        // Effective angles in radians including calibration trims
        const j1 = ((jointAngles.j1_base + trims.j1_base) * Math.PI) / 180;
        const j2 = ((jointAngles.j2_shoulder + trims.j2_shoulder) * Math.PI) / 180;
        const j3 = ((jointAngles.j3_elbow + trims.j3_elbow) * Math.PI) / 180;
        const j4 = ((jointAngles.j4_wrist + trims.j4_wrist) * Math.PI) / 180;
        const gripper = Math.max(0, Math.min(100, jointAngles.j5_gripper + trims.j5_gripper));

        // Base Origin
        const basePos = { x: 0, y: 0, z: 0 };

        // Shoulder Pivot
        const shoulderPos = { x: 0, y: this.BASE_HEIGHT, z: 0 };

        // Elbow Position (2D plane elevated by J2, rotated by J1)
        const r_elbow = this.SHOULDER_LEN * Math.cos(j2);
        const y_elbow = shoulderPos.y + this.SHOULDER_LEN * Math.sin(j2);
        const x_elbow = r_elbow * Math.sin(j1);
        const z_elbow = r_elbow * Math.cos(j1);
        const elbowPos = { x: x_elbow, y: y_elbow, z: z_elbow };

        // Wrist Position
        const a_elbow = j2 + j3;
        const r_wrist = r_elbow + this.ELBOW_LEN * Math.cos(a_elbow);
        const y_wrist = y_elbow + this.ELBOW_LEN * Math.sin(a_elbow);
        const x_wrist = r_wrist * Math.sin(j1);
        const z_wrist = r_wrist * Math.cos(j1);
        const wristPos = { x: x_wrist, y: y_wrist, z: z_wrist };

        // End Effector (Gripper Tip) Position
        const a_wrist = a_elbow + j4;
        const reach_eff = r_wrist + (this.WRIST_LEN + this.GRIPPER_LEN) * Math.cos(a_wrist);
        const y_eff = y_wrist + (this.WRIST_LEN + this.GRIPPER_LEN) * Math.sin(a_wrist);
        const x_eff = reach_eff * Math.sin(j1);
        const z_eff = reach_eff * Math.cos(j1);
        const endEffectorPos = { x: x_eff, y: y_eff, z: z_eff };

        return {
            base: basePos,
            shoulder: shoulderPos,
            elbow: elbowPos,
            wrist: wristPos,
            endEffector: endEffectorPos,
            anglesRad: { j1, j2, j3, j4, gripper }
        };
    }

    /**
     * Solves Inverse Kinematics (IK) to reach target 3D coordinate (x, y, z)
     */
    solveIK(targetX, targetY, targetZ, desiredPitchDeg = 0) {
        // Base Yaw J1
        const j1 = Math.atan2(targetX, targetZ);
        const r_target = Math.sqrt(targetX * targetX + targetZ * targetZ);

        const pitchRad = (desiredPitchDeg * Math.PI) / 180;
        const totalWristLen = this.WRIST_LEN + this.GRIPPER_LEN;

        // Wrist Center Location
        const r_wrist = r_target - totalWristLen * Math.cos(pitchRad);
        const y_wrist = targetY - totalWristLen * Math.sin(pitchRad) - this.BASE_HEIGHT;

        const d = Math.sqrt(r_wrist * r_wrist + y_wrist * y_wrist);

        const maxReach = this.SHOULDER_LEN + this.ELBOW_LEN - 1;
        const minReach = Math.abs(this.SHOULDER_LEN - this.ELBOW_LEN) + 1;

        if (d > maxReach || d < minReach) {
            return { reachable: false };
        }

        const alpha1 = Math.atan2(y_wrist, r_wrist);
        const cosAlpha2 = (this.SHOULDER_LEN * this.SHOULDER_LEN + d * d - this.ELBOW_LEN * this.ELBOW_LEN) / (2 * this.SHOULDER_LEN * d);
        const alpha2 = Math.acos(Math.max(-1, Math.min(1, cosAlpha2)));

        const j2 = alpha1 + alpha2;

        const cosBeta = (this.SHOULDER_LEN * this.SHOULDER_LEN + this.ELBOW_LEN * this.ELBOW_LEN - d * d) / (2 * this.SHOULDER_LEN * this.ELBOW_LEN);
        const beta = Math.acos(Math.max(-1, Math.min(1, cosBeta)));

        const j3 = beta - Math.PI;
        const j4 = pitchRad - (j2 + j3);

        return {
            reachable: true,
            j1_base: (j1 * 180) / Math.PI,
            j2_shoulder: (j2 * 180) / Math.PI,
            j3_elbow: (j3 * 180) / Math.PI,
            j4_wrist: (j4 * 180) / Math.PI
        };
    }

    /**
     * Updates dynamic animation trajectories for dance routines and poses
     */
    updateMotionRoutine(dt, now) {
        const j = { ...this.jointAngles };

        if (this.activePose === 'Wave Arm Dance') {
            j.j1_base = Math.sin(now * 0.005) * 45;
            j.j2_shoulder = 40 + Math.sin(now * 0.008) * 15;
            j.j3_elbow = 30 + Math.cos(now * 0.008) * 20;
            j.j4_wrist = Math.sin(now * 0.01) * 35;
            j.j5_gripper = 50 + Math.sin(now * 0.012) * 40;
        } else if (this.activePose === 'Arm Disco Dance') {
            j.j1_base = Math.cos(now * 0.006) * 60;
            j.j2_shoulder = 50 + Math.sin(now * 0.01) * 25;
            j.j3_elbow = -20 + Math.sin(now * 0.008) * 30;
            j.j4_wrist = Math.cos(now * 0.01) * 40;
            j.j5_gripper = 50 + Math.sin(now * 0.015) * 50;
        } else if (this.activePose === 'Scan Environment') {
            j.j1_base = Math.sin(now * 0.002) * 85;
            j.j2_shoulder = 25 + Math.sin(now * 0.003) * 10;
            j.j3_elbow = 0;
            j.j4_wrist = 0;
            j.j5_gripper = 30;
        } else if (this.activePose === 'Grab & Hold') {
            const pulseClaw = 50 + Math.sin(now * 0.008) * 40;
            j.j5_gripper = pulseClaw;
        } else if (this.activePose === 'Gesture Yes' || this.activePose === 'Yes') {
            j.j1_base = 0;
            j.j2_shoulder = 35 + Math.sin(now * 0.012) * 12;
            j.j3_elbow = 25 + Math.sin(now * 0.012) * 18;
            j.j4_wrist = 20 + Math.sin(now * 0.012) * 22;
            j.j5_gripper = 50;
        } else if (this.activePose === 'Gesture No' || this.activePose === 'No') {
            j.j1_base = Math.sin(now * 0.014) * 35;
            j.j2_shoulder = 25;
            j.j3_elbow = 30;
            j.j4_wrist = Math.cos(now * 0.014) * 25;
            j.j5_gripper = 50;
        } else if (this.activePose === 'High Five' || this.activePose === 'Hi Five') {
            j.j1_base = 0;
            j.j2_shoulder = 65 + Math.sin(now * 0.008) * 8;
            j.j3_elbow = 20 + Math.cos(now * 0.008) * 6;
            j.j4_wrist = 45;
            j.j5_gripper = 100;
        }

        return j;
    }
}

// Global Alias for backwards compatibility with HexapodKinematics references
window.HexapodKinematics = ArmKinematics;
