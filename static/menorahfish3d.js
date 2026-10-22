/**
 * Animatronic Menorah Fish & Candle Robot Arm Stage 3D Visualizer (Three.js)
 * Visualizes:
 * - Animatronic Fish with mouth lipsync, 3-second gradual horizontal neck swing, tail wagging, and head spotlight
 * - Mouth-side and Tail-side stage servos that sweep back and forth during speech
 * - 4 Stage Light Domes that breathe slowly in sequence while fish is talking
 * - 5-DOF Robot Arm with claw holding a CONSTANTLY LIT FLICKERING CANDLE
 * - 180-Degree Menorah Arc with 8 Side Candles + 1 Center Shamash Candle (lights stay ON when lit)
 * - Rotating Main Stage Base Turntable
 */

class MenorahFish3D {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        if (!this.container) return;

        try {
            this.scene = new THREE.Scene();
            this.scene.background = new THREE.Color(0x0a0f1d);

            const width = this.container.clientWidth || 800;
            const height = this.container.clientHeight || 500;

            this.camera = new THREE.PerspectiveCamera(45, width / height, 1, 3000);
            this.camera.position.set(0, 200, 390);

            try {
                this.renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
                this.renderer.shadowMap.enabled = true;
                this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
            } catch (rendererErr) {
                console.warn("Primary WebGLRenderer fallback to basic context:", rendererErr);
                this.renderer = new THREE.WebGLRenderer({ antialias: false });
            }
            this.renderer.setSize(width, height);
            this.container.appendChild(this.renderer.domElement);

            this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
            this.controls.enableDamping = true;
            this.controls.dampingFactor = 0.05;
            this.controls.target.set(0, 75, -20);

            const onResize = () => {
                if (!this.container || !this.renderer || !this.camera) return;
                const w = this.container.clientWidth || this.container.offsetWidth || 800;
                const h = this.container.clientHeight || this.container.offsetHeight || 480;
                if (w > 0 && h > 0) {
                    this.camera.aspect = w / h;
                    this.camera.updateProjectionMatrix();
                    this.renderer.setSize(w, h);
                }
            };

            window.addEventListener('resize', onResize);
            if (window.ResizeObserver) {
                const resizeObserver = new ResizeObserver(onResize);
                resizeObserver.observe(this.container);
            }
            setTimeout(onResize, 100);

            this.clock = new THREE.Clock();
            this.webglSupported = true;

            this.state = {
                is_speaking: false,
                fish: { mouth_motor: false, neck_position: 0.0, tail_motor: false, head_spotlight: true, mouth_side_servo: 90, tail_side_servo: 90 },
                robot_arm: { j1_base: 0, j2_shoulder: 30, j3_elbow: 45, j4_wrist: 0, j5_gripper: 50, claw_candle_flicker: true },
                menorah: { lit_count: 0, candles: [false, false, false, false, false, false, false, false, false] },
                light_domes: { breathing: false, mouth_side_dome1: 100, mouth_side_dome2: 100, tail_side_dome1: 100, tail_side_dome2: 100 },
                main_base: { servo_angle: 90 }
            };

            this.initLighting();
            this.buildStage();
            this.animate();
        } catch (err) {
            console.warn("WebGL initialization fallback:", err);
            this.webglSupported = false;
            this.container.innerHTML = `<div style="display:flex; flex-direction:column; align-items:center; justify-content:center; height:100%; color:#8a99ad; font-family:sans-serif; text-anchor:middle;">
                <p style="font-size:1.2rem; color:#ffd700; font-weight:bold;">🎭 3D Stage Visualizer Placeholder</p>
                <p style="font-size:0.85rem; margin-top:8px;">WebGL Context Disabled on this browser engine.</p>
            </div>`;
            return;
        }
    }

    setCameraView(viewName) {
        if (!this.webglSupported || !this.controls || !this.camera) return;
        if (viewName === 'top') {
            this.camera.position.set(0, 520, 20);
            this.controls.target.set(0, 0, 0);
        } else if (viewName === 'fish') {
            this.camera.position.set(0, 110, -50);
            this.controls.target.set(0, 75, -180);
        } else if (viewName === 'arm') {
            this.camera.position.set(0, 180, 280);
            this.controls.target.set(0, 50, 50);
        } else {
            this.camera.position.set(0, 220, 420);
            this.controls.target.set(0, 80, -40);
        }
        this.controls.update();
    }

    initLighting() {
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.45);
        this.scene.add(ambientLight);

        const dirLight = new THREE.DirectionalLight(0xfffaed, 0.85);
        dirLight.position.set(200, 400, 300);
        dirLight.castShadow = true;
        this.scene.add(dirLight);

        // Stage Blue Ambient Fill Light
        const stageLight = new THREE.PointLight(0x00f0ff, 0.6, 600);
        stageLight.position.set(0, 300, 100);
        this.scene.add(stageLight);
    }

    buildStage() {
        // Stationary Outer Base Ground Frame
        const outerBaseGeo = new THREE.CylinderGeometry(250, 260, 15, 64);
        const outerBaseMat = new THREE.MeshStandardMaterial({ color: 0x0a0e1a, roughness: 0.8 });
        const outerBaseMesh = new THREE.Mesh(outerBaseGeo, outerBaseMat);
        outerBaseMesh.position.y = -22;
        this.scene.add(outerBaseMesh);

        // Stage Root Group (Rotated by Main Base Servo Turntable)
        this.stageRoot = new THREE.Group();
        this.scene.add(this.stageRoot);

        // 1. Rotating Turntable Disc
        const baseGeo = new THREE.CylinderGeometry(225, 230, 18, 64);
        const baseMat = new THREE.MeshStandardMaterial({ color: 0x3d2612, roughness: 0.5, metalness: 0.2 });
        const baseMesh = new THREE.Mesh(baseGeo, baseMat);
        baseMesh.position.y = -9;
        baseMesh.receiveShadow = true;
        this.stageRoot.add(baseMesh);

        // Radial Wood Planks & Turntable Spokes for High Visual Contrast during Rotation
        const spokeMat = new THREE.MeshStandardMaterial({ color: 0xffaa00, metalness: 0.8, roughness: 0.2 });
        for (let i = 0; i < 12; i++) {
            const angle = (i / 12) * Math.PI * 2;
            const spoke = new THREE.Mesh(new THREE.BoxGeometry(8, 2, 210), spokeMat);
            spoke.rotation.y = angle;
            spoke.position.y = 0.5;
            this.stageRoot.add(spoke);

            // Perimeter Gear Teeth
            const tooth = new THREE.Mesh(new THREE.BoxGeometry(10, 10, 15), spokeMat);
            tooth.position.set(Math.sin(angle) * 225, 0, Math.cos(angle) * 225);
            this.stageRoot.add(tooth);
        }

        // Turntable Center Hub
        const hubMesh = new THREE.Mesh(
            new THREE.CylinderGeometry(35, 40, 8, 32),
            new THREE.MeshStandardMaterial({ color: 0x111122, metalness: 0.9 })
        );
        hubMesh.position.y = 1;
        this.stageRoot.add(hubMesh);

        // Perimeter Gold Trim Ring
        const trimMesh = new THREE.Mesh(new THREE.TorusGeometry(230, 4, 16, 64), new THREE.MeshStandardMaterial({ color: 0xffd700, metalness: 0.8 }));
        trimMesh.rotation.x = Math.PI / 2;
        trimMesh.position.y = 0.5;
        this.stageRoot.add(trimMesh);

        // 2. Build Animatronic Fish Assembly (Opposite Side: Z = -110)
        this.buildAnimatronicFish();

        // 3. Build 5-DOF Robot Arm with Constantly Flickering Candle in Claw
        this.buildRobotArm();

        // 4. Build 180-Degree Menorah Candle Arc (8 Side Candles + 1 Center Shamash Candle)
        this.buildMenorahCandleArc();

        // 5. Build 4 Light Domes (2 Mouth Side, 2 Tail Side)
        this.buildLightDomes();

        // 6. Build 3 Tall Pole Spotlights (Center Fish Plaque Spotlight + Left & Right Dreidel Servo Spotlights)
        this.build3TallPoleSpotlights();
    }

    buildAnimatronicFish() {
        this.fishRoot = new THREE.Group();
        this.fishRoot.position.set(0, 0, -180); // Plaque stands on back edge of stage
        this.stageRoot.add(this.fishRoot);

        // --- ENLARGED GEMMY OVAL WOODEN WALL PLAQUE (1.8x LARGER) ---
        const plaqueGroup = new THREE.Group();
        plaqueGroup.position.set(0, 85, 0); // Plaque front surface at Z = 0
        this.fishRoot.add(plaqueGroup);

        // Polished Oval Wooden Backboard
        const plaqueGeo = new THREE.CylinderGeometry(110, 110, 12, 64);
        plaqueGeo.scale(1.6, 1.05, 0.8);
        const plaqueMat = new THREE.MeshStandardMaterial({ color: 0x4a2410, roughness: 0.3, metalness: 0.1 });
        const plaqueMesh = new THREE.Mesh(plaqueGeo, plaqueMat);
        plaqueMesh.rotation.x = Math.PI / 2;
        plaqueGroup.add(plaqueMesh);

        // Plaque Brass Trim Bezel Ring
        const trimMesh = new THREE.Mesh(
            new THREE.TorusGeometry(108, 4, 16, 64),
            new THREE.MeshStandardMaterial({ color: 0xffd700, metalness: 0.9, roughness: 0.1 })
        );
        trimMesh.position.z = 6;
        plaqueGroup.add(trimMesh);

        // Brass Nameplate ("GEMMY ANIMATRONIC SINGING TROUT")
        const nameplateMesh = new THREE.Mesh(
            new THREE.BoxGeometry(110, 22, 3),
            new THREE.MeshStandardMaterial({ color: 0xcc9900, metalness: 0.9 })
        );
        nameplateMesh.position.set(0, -70, 7);
        plaqueGroup.add(nameplateMesh);

        // Plaque Mounting Stand Posts
        for (let side of [-75, 75]) {
            const postMesh = new THREE.Mesh(
                new THREE.CylinderGeometry(8, 9, 100, 16),
                new THREE.MeshStandardMaterial({ color: 0x111a28, metalness: 0.8 })
            );
            postMesh.position.set(side, -50, -6);
            this.fishRoot.add(postMesh);
        }

        // Dedicated High-Intensity Plaque & Trout Spotlight
        const plaqueTarget = new THREE.Object3D();
        plaqueTarget.position.set(0, 85, 0);
        this.fishRoot.add(plaqueTarget);

        const plaqueLight = new THREE.SpotLight(0xfff5ea, 6.0, 500, Math.PI / 3, 0.2);
        plaqueLight.position.set(0, 180, 150);
        plaqueLight.target = plaqueTarget;
        this.fishRoot.add(plaqueLight);

        // --- FISH NECK SWING HINGE (MOUNTED ON FRONT SURFACE OF PLAQUE) ---
        this.fishNeckGroup = new THREE.Group();
        this.fishNeckGroup.position.set(-35, 85, 14); // Mounted on FRONT surface of plaque
        this.fishRoot.add(this.fishNeckGroup);

        // Mechanical Hinge Arm
        const hingeArm = new THREE.Mesh(
            new THREE.BoxGeometry(24, 18, 55),
            new THREE.MeshStandardMaterial({ color: 0x778899, metalness: 0.8 })
        );
        hingeArm.position.set(0, 0, 27.5);
        this.fishNeckGroup.add(hingeArm);

        // --- ENLARGED GEMMY SINGING TROUT BODY, HEAD & TAIL (2.2x LARGER) ---
        this.fishHeadGroup = new THREE.Group();
        this.fishHeadGroup.position.set(0, 0, 55); // All geometry in FRONT of plaque
        this.fishNeckGroup.add(this.fishHeadGroup);

        // Trout Main Body (Mounted horizontally on front surface of plaque)
        const bodyGeo = new THREE.SphereGeometry(48, 32, 16);
        bodyGeo.scale(2.2, 1.25, 0.85); // Scaled horizontally along plaque
        const bodyMat = new THREE.MeshStandardMaterial({ color: 0x2e8b57, metalness: 0.6, roughness: 0.2 });
        const bodyMesh = new THREE.Mesh(bodyGeo, bodyMat);
        bodyMesh.position.set(0, 0, 0);
        this.fishHeadGroup.add(bodyMesh);

        // Trout Iridescent Lateral Pink/Gold Stripe
        const stripeMesh = new THREE.Mesh(
            new THREE.BoxGeometry(150, 16, 30),
            new THREE.MeshStandardMaterial({ color: 0xff1493, metalness: 0.8, roughness: 0.1 })
        );
        stripeMesh.position.set(0, 0, 6);
        this.fishHeadGroup.add(stripeMesh);

        // Trout Belly (White / Silver)
        const bellyMesh = new THREE.Mesh(
            new THREE.SphereGeometry(40, 32, 16),
            new THREE.MeshStandardMaterial({ color: 0xf5f8ff, roughness: 0.3 })
        );
        bellyMesh.position.set(0, -18, 4);
        bellyMesh.scale.set(1.8, 0.8, 0.8);
        this.fishHeadGroup.add(bellyMesh);

        // Trout Dorsal Fin (Top Fin)
        const dorsalGeo = new THREE.ConeGeometry(18, 45, 16);
        dorsalGeo.scale(1.2, 1.0, 0.15);
        const dorsalMesh = new THREE.Mesh(dorsalGeo, new THREE.MeshStandardMaterial({ color: 0x228b22, metalness: 0.6 }));
        dorsalMesh.position.set(-10, 52, 0);
        dorsalMesh.rotation.z = -0.3;
        this.fishHeadGroup.add(dorsalMesh);

        // Trout Pectoral Fins (Front Fins)
        for (let side of [-1, 1]) {
            const finMesh = new THREE.Mesh(
                new THREE.BoxGeometry(32, 3, 24),
                new THREE.MeshStandardMaterial({ color: 0x3cb371, metalness: 0.5 })
            );
            finMesh.position.set(-35, -18, side * 24);
            finMesh.rotation.z = -0.4;
            this.fishHeadGroup.add(finMesh);
        }

        // Trout Eyes
        for (let side of [-1, 1]) {
            const eyeGroup = new THREE.Group();
            eyeGroup.position.set(-60, 14, side * 22);
            this.fishHeadGroup.add(eyeGroup);

            const eyeSocket = new THREE.Mesh(new THREE.SphereGeometry(10, 16, 16), new THREE.MeshStandardMaterial({ color: 0xffd700, metalness: 0.9 }));
            eyeGroup.add(eyeSocket);

            const pupil = new THREE.Mesh(new THREE.SphereGeometry(5.5, 16, 16), new THREE.MeshBasicMaterial({ color: 0x000000 }));
            pupil.position.z = side * 5.5;
            eyeGroup.add(pupil);
        }

        // ENLARGED ARTICULATING MOUTH / BEAK (DRAMATIC LIPSYNC MOTION)
        this.fishMouthMesh = new THREE.Mesh(
            new THREE.ConeGeometry(30, 48, 16),
            new THREE.MeshStandardMaterial({ color: 0x3cb371, metalness: 0.5 })
        );
        this.fishMouthMesh.rotation.z = Math.PI / 2;
        this.fishMouthMesh.position.set(-82, -6, 0);
        this.fishHeadGroup.add(this.fishMouthMesh);

        // Fish Head Spotlight
        const fishHeadTarget = new THREE.Object3D();
        fishHeadTarget.position.set(-82, -6, 0);
        this.fishHeadGroup.add(fishHeadTarget);
        this.fishSpotlight = new THREE.SpotLight(0x00f0ff, 5.0, 400, Math.PI / 4, 0.3);
        this.fishSpotlight.position.set(-82, 45, 30);
        this.fishSpotlight.target = fishHeadTarget;
        this.fishHeadGroup.add(this.fishSpotlight);

        // ENLARGED TAIL MOTOR & LARGE CAUDAL TAIL FIN (DRAMATIC TAIL WAGGING)
        this.fishTailGroup = new THREE.Group();
        this.fishTailGroup.position.set(75, 0, 0);
        this.fishHeadGroup.add(this.fishTailGroup);

        const finGeo = new THREE.ConeGeometry(40, 80, 16);
        finGeo.scale(1.3, 1.3, 0.25);
        const finMesh = new THREE.Mesh(finGeo, new THREE.MeshStandardMaterial({ color: 0x228b22, metalness: 0.7 }));
        finMesh.rotation.z = -Math.PI / 2;
        this.fishTailGroup.add(finMesh);

        // Dreidel Left Servo Motor & Spinning Dreidel (PCA Ch 3)
        this.dreidelLeftServoGroup = new THREE.Group();
        this.dreidelLeftServoGroup.position.set(-85, 0, -80);
        this.stageRoot.add(this.dreidelLeftServoGroup);
        const lServoMesh = new THREE.Mesh(new THREE.BoxGeometry(22, 35, 22), new THREE.MeshStandardMaterial({ color: 0x112244, metalness: 0.8 }));
        lServoMesh.position.y = 17.5;
        this.dreidelLeftServoGroup.add(lServoMesh);

        // Dreidel on Top of Left Servo
        this.leftDreidelGroup = this.buildDreidel(0x00f0ff); // Glowing Cyan Dreidel
        this.leftDreidelGroup.position.y = 35;
        this.dreidelLeftServoGroup.add(this.leftDreidelGroup);

        // Dreidel Right Servo Motor & Spinning Dreidel (PCA Ch 4)
        this.dreidelRightServoGroup = new THREE.Group();
        this.dreidelRightServoGroup.position.set(85, 0, -80);
        this.stageRoot.add(this.dreidelRightServoGroup);
        const rServoMesh = new THREE.Mesh(new THREE.BoxGeometry(22, 35, 22), new THREE.MeshStandardMaterial({ color: 0x112244, metalness: 0.8 }));
        rServoMesh.position.y = 17.5;
        this.dreidelRightServoGroup.add(rServoMesh);

        // Dreidel on Top of Right Servo
        this.rightDreidelGroup = this.buildDreidel(0xff00cc); // Glowing Magenta Dreidel
        this.rightDreidelGroup.position.y = 35;
        this.dreidelRightServoGroup.add(this.rightDreidelGroup);
    }

    build3TallPoleSpotlights() {
        // 1. Center Fish Mouth Pole Spotlight (Tall pole illuminating the fish mouth at X=0, Z=-215)
        const centerPoleGroup = new THREE.Group();
        centerPoleGroup.position.set(0, 0, -215);
        this.stageRoot.add(centerPoleGroup);

        const centerBase = new THREE.Mesh(new THREE.CylinderGeometry(16, 20, 10, 32), new THREE.MeshStandardMaterial({ color: 0x111a28, metalness: 0.9 }));
        centerBase.position.y = 5;
        centerPoleGroup.add(centerBase);

        const centerPole = new THREE.Mesh(new THREE.CylinderGeometry(5, 6, 210, 16), new THREE.MeshStandardMaterial({ color: 0x8899aa, metalness: 0.9, roughness: 0.1 }));
        centerPole.position.y = 105;
        centerPoleGroup.add(centerPole);

        const centerArm = new THREE.Mesh(new THREE.BoxGeometry(8, 8, 50), new THREE.MeshStandardMaterial({ color: 0x334455, metalness: 0.8 }));
        centerArm.position.set(0, 205, 20);
        centerPoleGroup.add(centerArm);

        const centerLamp = new THREE.Mesh(new THREE.ConeGeometry(18, 30, 16), new THREE.MeshStandardMaterial({ color: 0x223344, metalness: 0.8 }));
        centerLamp.position.set(0, 195, 42);
        centerLamp.rotation.x = Math.PI / 3;
        centerPoleGroup.add(centerLamp);

        const centerTarget = new THREE.Object3D();
        centerTarget.position.set(0, 85, -120);
        this.stageRoot.add(centerTarget);

        this.centerFishSpotlight = new THREE.SpotLight(0xfff5ea, 6.0, 500, Math.PI / 3, 0.2);
        this.centerFishSpotlight.position.set(0, 195, -170);
        this.centerFishSpotlight.target = centerTarget;
        this.stageRoot.add(this.centerFishSpotlight);

        // 2. Left Dreidel Servo Pole Spotlight (Tall pole illuminating Left Dreidel at X=-85, Z=-80)
        const leftPoleGroup = new THREE.Group();
        leftPoleGroup.position.set(-125, 0, -110);
        this.stageRoot.add(leftPoleGroup);

        const leftBase = new THREE.Mesh(new THREE.CylinderGeometry(14, 18, 8, 32), new THREE.MeshStandardMaterial({ color: 0x111a28, metalness: 0.9 }));
        leftBase.position.y = 4;
        leftPoleGroup.add(leftBase);

        const leftPole = new THREE.Mesh(new THREE.CylinderGeometry(4, 5, 170, 16), new THREE.MeshStandardMaterial({ color: 0x8899aa, metalness: 0.9 }));
        leftPole.position.y = 85;
        leftPoleGroup.add(leftPole);

        const leftArm = new THREE.Mesh(new THREE.BoxGeometry(6, 6, 35), new THREE.MeshStandardMaterial({ color: 0x334455, metalness: 0.8 }));
        leftArm.position.set(15, 165, 15);
        leftArm.rotation.y = -Math.PI / 4;
        leftPoleGroup.add(leftArm);

        const leftLamp = new THREE.Mesh(new THREE.ConeGeometry(14, 22, 16), new THREE.MeshStandardMaterial({ color: 0x223344, metalness: 0.8 }));
        leftLamp.position.set(25, 158, 25);
        leftLamp.rotation.x = Math.PI / 3;
        leftPoleGroup.add(leftLamp);

        const leftTarget = new THREE.Object3D();
        leftTarget.position.set(-85, 35, -80);
        this.stageRoot.add(leftTarget);

        this.leftDreidelSpotlight = new THREE.SpotLight(0x00f0ff, 4.0, 300, Math.PI / 4, 0.25);
        this.leftDreidelSpotlight.position.set(-100, 158, -85);
        this.leftDreidelSpotlight.target = leftTarget;
        this.stageRoot.add(this.leftDreidelSpotlight);

        // 3. Right Dreidel Servo Pole Spotlight (Tall pole illuminating Right Dreidel at X=+85, Z=-80)
        const rightPoleGroup = new THREE.Group();
        rightPoleGroup.position.set(125, 0, -110);
        this.stageRoot.add(rightPoleGroup);

        const rightBase = new THREE.Mesh(new THREE.CylinderGeometry(14, 18, 8, 32), new THREE.MeshStandardMaterial({ color: 0x111a28, metalness: 0.9 }));
        rightBase.position.y = 4;
        rightPoleGroup.add(rightBase);

        const rightPole = new THREE.Mesh(new THREE.CylinderGeometry(4, 5, 170, 16), new THREE.MeshStandardMaterial({ color: 0x8899aa, metalness: 0.9 }));
        rightPole.position.y = 85;
        rightPoleGroup.add(rightPole);

        const rightArm = new THREE.Mesh(new THREE.BoxGeometry(6, 6, 35), new THREE.MeshStandardMaterial({ color: 0x334455, metalness: 0.8 }));
        rightArm.position.set(-15, 165, 15);
        rightArm.rotation.y = Math.PI / 4;
        rightPoleGroup.add(rightArm);

        const rightLamp = new THREE.Mesh(new THREE.ConeGeometry(14, 22, 16), new THREE.MeshStandardMaterial({ color: 0x223344, metalness: 0.8 }));
        rightLamp.position.set(-25, 158, 25);
        rightLamp.rotation.x = Math.PI / 3;
        rightPoleGroup.add(rightLamp);

        const rightTarget = new THREE.Object3D();
        rightTarget.position.set(85, 35, -80);
        this.stageRoot.add(rightTarget);

        this.rightDreidelSpotlight = new THREE.SpotLight(0xff00cc, 4.0, 300, Math.PI / 4, 0.25);
        this.rightDreidelSpotlight.position.set(100, 158, -85);
        this.rightDreidelSpotlight.target = rightTarget;
        this.stageRoot.add(this.rightDreidelSpotlight);
    }

    buildDreidel(colorHex) {
        const dreidelGroup = new THREE.Group();

        // 1. Top Handle Stem
        const stemMesh = new THREE.Mesh(
            new THREE.CylinderGeometry(2.5, 2.5, 14, 16),
            new THREE.MeshStandardMaterial({ color: 0xffd700, metalness: 0.9, roughness: 0.1 })
        );
        stemMesh.position.y = 22;
        dreidelGroup.add(stemMesh);

        // 2. Square 4-Sided Dreidel Body Block
        const bodyMesh = new THREE.Mesh(
            new THREE.BoxGeometry(18, 18, 18),
            new THREE.MeshStandardMaterial({ color: colorHex, metalness: 0.6, roughness: 0.2 })
        );
        bodyMesh.position.y = 9;
        dreidelGroup.add(bodyMesh);

        // Gold Trim Bezel on Body Edges
        const frameMesh = new THREE.Mesh(
            new THREE.BoxGeometry(19, 1, 19),
            new THREE.MeshStandardMaterial({ color: 0xffd700, metalness: 0.9 })
        );
        frameMesh.position.y = 18;
        dreidelGroup.add(frameMesh);

        // 3. Inverted Pyramid Bottom Tip
        const tipMesh = new THREE.Mesh(
            new THREE.ConeGeometry(12.7, 16, 4),
            new THREE.MeshStandardMaterial({ color: 0xffd700, metalness: 0.8, roughness: 0.2 })
        );
        tipMesh.rotation.x = Math.PI; // Inverted pyramid tip
        tipMesh.rotation.y = Math.PI / 4; // Align flat with body
        tipMesh.position.y = -8;
        dreidelGroup.add(tipMesh);

        return dreidelGroup;
    }

    buildRobotArm() {
        this.armRoot = new THREE.Group();
        this.armRoot.position.set(0, 0, 0); // Stage Center
        this.stageRoot.add(this.armRoot);

        // Joint 1: Base Servo (Yaw)
        const basePlate = new THREE.Mesh(new THREE.CylinderGeometry(25, 30, 12, 32), new THREE.MeshStandardMaterial({ color: 0x222233, metalness: 0.8 }));
        basePlate.position.y = 6;
        this.armRoot.add(basePlate);

        this.armJ1Group = new THREE.Group();
        this.armJ1Group.position.y = 12;
        this.armRoot.add(this.armJ1Group);

        // Joint 2: Shoulder
        this.armJ2Group = new THREE.Group();
        this.armJ2Group.position.y = 15;
        this.armJ1Group.add(this.armJ2Group);

        const bicepMesh = new THREE.Mesh(new THREE.BoxGeometry(10, 65, 10), new THREE.MeshStandardMaterial({ color: 0xff9900, metalness: 0.6 }));
        bicepMesh.position.y = 32.5;
        this.armJ2Group.add(bicepMesh);

        // Joint 3: Elbow
        this.armJ3Group = new THREE.Group();
        this.armJ3Group.position.y = 65;
        this.armJ2Group.add(this.armJ3Group);

        const forearmMesh = new THREE.Mesh(new THREE.BoxGeometry(8, 55, 8), new THREE.MeshStandardMaterial({ color: 0xffaa00, metalness: 0.6 }));
        forearmMesh.position.y = 27.5;
        this.armJ3Group.add(forearmMesh);

        // Joint 4: Wrist
        this.armJ4Group = new THREE.Group();
        this.armJ4Group.position.y = 55;
        this.armJ3Group.add(this.armJ4Group);

        // Joint 5: Claw Gripper holding Candle
        this.armClawGroup = new THREE.Group();
        this.armClawGroup.position.y = 20;
        this.armJ4Group.add(this.armClawGroup);

        const clawMesh = new THREE.Mesh(new THREE.BoxGeometry(16, 8, 16), new THREE.MeshStandardMaterial({ color: 0x333344, metalness: 0.9 }));
        this.armClawGroup.add(clawMesh);

        // CONSTANTLY LIT FLICKERING CANDLE IN CLAW!
        const clawCandleMesh = new THREE.Mesh(new THREE.CylinderGeometry(3, 3, 25, 16), new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.2 }));
        clawCandleMesh.position.y = 16.5;
        this.armClawGroup.add(clawCandleMesh);

        // Flickering Flame Bulb
        this.clawFlameMesh = new THREE.Mesh(
            new THREE.SphereGeometry(4, 16, 16),
            new THREE.MeshStandardMaterial({ color: 0xff5500, emissive: 0xffaa00, emissiveIntensity: 1.0 })
        );
        this.clawFlameMesh.position.y = 31;
        this.armClawGroup.add(this.clawFlameMesh);

        this.clawFlameLight = new THREE.PointLight(0xffaa00, 2.5, 120);
        this.clawFlameLight.position.y = 31;
        this.armClawGroup.add(this.clawFlameLight);
    }

    buildMenorahCandleArc() {
        this.menorahGroup = new THREE.Group();
        this.stageRoot.add(this.menorahGroup);

        this.candleObjs = [];
        // 180° Arc Candle Positions (Index 0 to 8: 8 Side Candles + Index 4 Center Shamash Candle)
        const arcAngles = [-80, -60, -40, -20, 0, 20, 40, 60, 80];
        const arcRadius = 150;

        arcAngles.forEach((deg, idx) => {
            const rad = deg * (Math.PI / 180);
            const isShamash = (idx === 4);
            const x = Math.sin(rad) * arcRadius;
            const z = Math.cos(rad) * arcRadius;

            const candleGroup = new THREE.Group();
            candleGroup.position.set(x, 0, z);
            this.menorahGroup.add(candleGroup);

            // Brass Candle Holder Stand
            const hHeight = isShamash ? 45 : 30;
            const holderMesh = new THREE.Mesh(
                new THREE.CylinderGeometry(5, 7, hHeight, 16),
                new THREE.MeshStandardMaterial({ color: 0xffd700, metalness: 0.8, roughness: 0.2 })
            );
            holderMesh.position.y = hHeight / 2;
            candleGroup.add(holderMesh);

            // White Candle Body
            const cHeight = isShamash ? 40 : 30;
            const candleMesh = new THREE.Mesh(
                new THREE.CylinderGeometry(3.5, 3.5, cHeight, 16),
                new THREE.MeshStandardMaterial({ color: 0xfffdf0, roughness: 0.3 })
            );
            candleMesh.position.y = hHeight + cHeight / 2;
            candleGroup.add(candleMesh);

            // Flickering Light Bulb Flame on Top
            const flameGeo = new THREE.SphereGeometry(3.5, 16, 16);
            flameGeo.scale(0.8, 1.5, 0.8);
            const flameMat = new THREE.MeshStandardMaterial({ color: 0xff3300, emissive: 0xff8800, emissiveIntensity: 0.0 });
            const flameMesh = new THREE.Mesh(flameGeo, flameMat);
            flameMesh.position.y = hHeight + cHeight + 5;
            candleGroup.add(flameMesh);

            // Candle Light Pointlight
            const candleLight = new THREE.PointLight(0xffaa00, 0.0, 100);
            candleLight.position.y = hHeight + cHeight + 5;
            candleGroup.add(candleLight);

            this.candleObjs.push({ group: candleGroup, flameMesh: flameMesh, flameMat: flameMat, candleLight: candleLight, isShamash: isShamash });
        });
    }

    buildLightDomes() {
        this.lightDomes = [];

        // 2 Mouth-Side Light Domes (between mouth-side servo X=-80, Z=-80 and end of candle arc)
        // 2 Tail-Side Light Domes (between tail-side servo X=+80, Z=-80 and beginning of candle arc)
        const domePos = [
            { x: -110, z: -20, name: "mouth1" },
            { x: -130, z: 40,  name: "mouth2" },
            { x: 110,  z: -20, name: "tail1" },
            { x: 130,  z: 40,  name: "tail2" }
        ];

        domePos.forEach(p => {
            const domeGroup = new THREE.Group();
            domeGroup.position.set(p.x, 0, p.z);
            this.stageRoot.add(domeGroup);

            // Base Ring
            const baseMesh = new THREE.Mesh(new THREE.CylinderGeometry(14, 16, 6, 32), new THREE.MeshStandardMaterial({ color: 0x111625, metalness: 0.8 }));
            baseMesh.position.y = 3;
            domeGroup.add(baseMesh);

            // Frosted Glass Light Dome
            const domeMat = new THREE.MeshStandardMaterial({ color: 0x00f0ff, emissive: 0x00f0ff, emissiveIntensity: 0.6, transparent: true, opacity: 0.85 });
            const domeMesh = new THREE.Mesh(new THREE.SphereGeometry(12, 32, 16, 0, Math.PI * 2, 0, Math.PI / 2), domeMat);
            domeMesh.position.y = 6;
            domeGroup.add(domeMesh);

            // Dome Pointlight
            const domeLight = new THREE.PointLight(0x00f0ff, 1.5, 120);
            domeLight.position.y = 12;
            domeGroup.add(domeLight);

            this.lightDomes.push({ group: domeGroup, domeMat: domeMat, domeLight: domeLight, name: p.name });
        });
    }

    updateState(newState) {
        if (!this.webglSupported || !newState) return;

        if (newState.is_speaking !== undefined) this.state.is_speaking = newState.is_speaking;
        if (newState.is_dancing !== undefined) this.state.is_dancing = newState.is_dancing;
        if (newState.fish) Object.assign(this.state.fish, newState.fish);
        if (newState.robot_arm) Object.assign(this.state.robot_arm, newState.robot_arm);
        if (newState.menorah) Object.assign(this.state.menorah, newState.menorah);
        if (newState.light_domes) Object.assign(this.state.light_domes, newState.light_domes);
        if (newState.main_base) Object.assign(this.state.main_base, newState.main_base);
    }

    animate() {
        if (!this.webglSupported) return;
        requestAnimationFrame(() => this.animate());

        const time = this.clock.getElapsedTime();
        this.controls.update();

        // 1. Stationary Fixed Stage Base (No Base Servo)
        if (this.stageRoot) {
            this.stageRoot.rotation.y = 0;
        }

        // 2. Animate Animatronic Fish Mechanics
        const fish = this.state.fish;
        const isSpeaking = !!this.state.is_speaking || !!fish.mouth_motor;
        const isDancing = !!this.state.is_dancing;

        // As the fish talks, its neck comes out slowly
        if (this.fishNeckGroup) {
            const restAngle = Math.PI / 3.2; // Angled rest stance against plaque
            if (isSpeaking) {
                if (fish.neck_position < 1.0) fish.neck_position = Math.min(1.0, fish.neck_position + 0.02);
            } else if (!isDancing) {
                if (fish.neck_position > 0.0) fish.neck_position = Math.max(0.0, fish.neck_position - 0.02);
            }
            const targetRad = restAngle - (fish.neck_position * (Math.PI / 3.2)); // Swings outward facing camera
            this.fishNeckGroup.rotation.y += (targetRad - this.fishNeckGroup.rotation.y) * 0.08;
        }

        // Mouth Beak Lipsync Motion
        if (this.fishMouthMesh) {
            const mouthScale = (fish.mouth_motor || isSpeaking) ? (1.0 + Math.abs(Math.sin(time * 16)) * 0.5) : 1.0;
            this.fishMouthMesh.scale.set(1.0, mouthScale, 1.0);
        }

        // As the fish talks, its tail wags
        if (this.fishTailGroup) {
            const tailSwing = (fish.tail_motor || isSpeaking || isDancing) ? Math.sin(time * 12) * 0.45 : Math.sin(time * 2) * 0.08;
            this.fishTailGroup.rotation.y = tailSwing;
        }

        // 3 Tall Pole Spotlights:
        // 1 illuminating left dreidel, 1 illuminating right dreidel, 1 illuminating fish's mouth!
        // These lights illuminate when the fish talks!
        const spotIntensity = isSpeaking ? 8.0 : 1.0;
        if (this.fishSpotlight) this.fishSpotlight.intensity = isSpeaking ? 6.0 : 0.8;
        if (this.centerFishSpotlight) this.centerFishSpotlight.intensity = spotIntensity;
        if (this.leftDreidelSpotlight) this.leftDreidelSpotlight.intensity = spotIntensity;
        if (this.rightDreidelSpotlight) this.rightDreidelSpotlight.intensity = spotIntensity;

        // When the fish starts speaking, the 2 dreidel servos sweep back and forth!
        if (this.dreidelLeftServoGroup && this.dreidelRightServoGroup) {
            if (isSpeaking || isDancing) {
                const sweepAngleLeft = Math.sin(time * 4.0) * (Math.PI / 3);
                const sweepAngleRight = Math.cos(time * 4.0) * (Math.PI / 3);
                this.dreidelLeftServoGroup.rotation.y = sweepAngleLeft;
                this.dreidelRightServoGroup.rotation.y = sweepAngleRight;
            } else {
                this.dreidelLeftServoGroup.rotation.y += (0 - this.dreidelLeftServoGroup.rotation.y) * 0.1;
                this.dreidelRightServoGroup.rotation.y += (0 - this.dreidelRightServoGroup.rotation.y) * 0.1;
            }
        }

        // Dreidels spin on top of servos
        if (this.leftDreidelGroup && this.rightDreidelGroup) {
            if (isSpeaking || isDancing) {
                this.leftDreidelGroup.rotation.y += 0.15;
                this.rightDreidelGroup.rotation.y += 0.15;
            } else {
                this.leftDreidelGroup.rotation.y += 0.02;
                this.rightDreidelGroup.rotation.y += 0.02;
            }
        }

        // 3. Animate 5-DOF Robot Arm
        const arm = this.state.robot_arm;
        if (this.armJ1Group) this.armJ1Group.rotation.y += ((arm.j1_base * Math.PI / 180) - this.armJ1Group.rotation.y) * 0.1;
        if (this.armJ2Group) this.armJ2Group.rotation.z += ((arm.j2_shoulder * Math.PI / 180) - this.armJ2Group.rotation.z) * 0.1;
        if (this.armJ3Group) this.armJ3Group.rotation.z += ((arm.j3_elbow * Math.PI / 180) - this.armJ3Group.rotation.z) * 0.1;
        if (this.armJ4Group) this.armJ4Group.rotation.z += ((arm.j4_wrist * Math.PI / 180) - this.armJ4Group.rotation.z) * 0.1;

        // Claw Candle Flickering Flame (ALWAYS ON)
        if (this.clawFlameMesh && this.clawFlameLight) {
            const flicker = 0.85 + Math.sin(time * 18) * 0.15;
            this.clawFlameMesh.scale.set(flicker, flicker * 1.1, flicker);
            this.clawFlameLight.intensity = 2.5 * flicker;
        }

        // 4. Animate Menorah Candles (Light bulbs STAY ON when lit)
        if (this.candleObjs && this.state.menorah.candles) {
            this.candleObjs.forEach((obj, idx) => {
                const isLit = !!this.state.menorah.candles[idx];
                const flicker = isLit ? (0.8 + Math.sin(time * 14 + idx) * 0.2) : 0.0;
                obj.flameMat.emissiveIntensity = isLit ? (0.9 + flicker * 0.3) : 0.0;
                obj.candleLight.intensity = isLit ? (2.0 + flicker) : 0.0;
            });
        }

        // 5. Animate 4 Light Domes on the Round Stage:
        // - Breathe in unison when the fish talks
        // - Do light chases when the fish dances to the music!
        if (this.lightDomes) {
            if (isDancing) {
                // Sequential running chase pattern around the 4 stage domes when dancing to music
                const chaseIndex = Math.floor((time * 6.0) % 4);
                this.lightDomes.forEach((d, idx) => {
                    const isLit = (idx === chaseIndex);
                    d.domeMat.opacity = isLit ? 0.95 : 0.2;
                    d.domeLight.intensity = isLit ? 3.5 : 0.3;
                });
            } else if (isSpeaking) {
                // Breathe in unison when the fish talks (smooth sync pulse for all 4 domes together)
                const unisonPulse = 0.35 + 0.65 * (0.5 + 0.5 * Math.sin(time * 3.5));
                this.lightDomes.forEach(d => {
                    d.domeMat.opacity = unisonPulse * 0.9;
                    d.domeLight.intensity = unisonPulse * 3.0;
                });
            } else {
                // Idle ambient glow
                this.lightDomes.forEach(d => {
                    d.domeMat.opacity = 0.3;
                    d.domeLight.intensity = 0.5;
                });
            }
        }

        this.renderer.render(this.scene, this.camera);
    }
}

window.MenorahFish3D = MenorahFish3D;
