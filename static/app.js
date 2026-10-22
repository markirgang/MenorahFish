/**
 * Animatronic Menorah Fish & Candle Lighting Robot Arm Master Web Application
 */

function startApp() {
    // 1. Initialize 3D Visualizer (Safely wrapped)
    let visualizer = null;
    try {
        visualizer = new MenorahFish3D('stage3dContainer');
        window.visualizer = visualizer;
    } catch (e) {
        console.warn("3D Visualizer initialization bypassed:", e);
    }

    // State object
    let localState = {
        is_speaking: false,
        active_voice: "ai_male_us",
        fish: {
            mouth_motor: false,
            neck_motor_pwm: 0,
            neck_position: 0.0,
            tail_motor: false,
            head_spotlight: true,
            mouth_side_servo: 90,
            tail_side_servo: 90
        },
        robot_arm: {
            j1_base: 0,
            j2_shoulder: 30,
            j3_elbow: 45,
            j4_wrist: 0,
            j5_gripper: 50,
            claw_candle_flicker: true
        },
        menorah: {
            lit_count: 0,
            candles: [false, false, false, false, false, false, false, false, false]
        },
        light_domes: {
            breathing: false,
            mouth_side_dome1: 100,
            mouth_side_dome2: 100,
            tail_side_dome1: 100,
            tail_side_dome2: 100
        },
        main_base: { servo_angle: 90, random_moving: true }
    };

    // Helper for POST requests
    function sendPost(endpoint, data, callback) {
        fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        })
        .then(r => r.json())
        .then(res => { if (callback) callback(res); })
        .catch(err => console.error("POST error:", endpoint, err));
    }

    // --- 2. MENORAH CANDLE LIGHTING SELECTOR ---
    const menorahStatusText = document.getElementById('menorahStatusText');
    const candleButtons = document.querySelectorAll('.btn-light-candle');

    function triggerLightCandles(count) {
        if (menorahStatusText) {
            menorahStatusText.textContent = (count === 0) ? "Extinguishing All Menorah Candles..." : `Lighting ${count} Hanukkah Candles with Robot Arm...`;
        }
        sendPost('/api/menorah/light_candles', { count: parseInt(count) });
    }

    candleButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const count = btn.getAttribute('data-count');
            triggerLightCandles(count);
        });
    });

    // --- 3. ANIMATRONIC FISH & ROBOT ARM EVENT LISTENERS ---
    const btnFishMouth = document.getElementById('btnFishMouth');
    const btnFishNeckSwing = document.getElementById('btnFishNeckSwing');
    const btnFishTailWag = document.getElementById('btnFishTailWag');
    const btnFishSpotlight = document.getElementById('btnFishSpotlight');
    const btnFishSideServos = document.getElementById('btnFishSideServos');

    if (btnFishMouth) {
        btnFishMouth.addEventListener('click', () => {
            localState.fish.mouth_motor = !localState.fish.mouth_motor;
            btnFishMouth.classList.toggle('active', localState.fish.mouth_motor);
            sendPost('/api/menorah/state_update', { fish: { mouth_motor: localState.fish.mouth_motor } });
        });
    }

    if (btnFishNeckSwing) {
        btnFishNeckSwing.addEventListener('click', () => {
            localState.is_speaking = !localState.is_speaking;
            btnFishNeckSwing.classList.toggle('active', localState.is_speaking);
            sendPost('/api/menorah/state_update', { is_speaking: localState.is_speaking });
        });
    }

    if (btnFishTailWag) {
        btnFishTailWag.addEventListener('click', () => {
            localState.fish.tail_motor = !localState.fish.tail_motor;
            btnFishTailWag.classList.toggle('active', localState.fish.tail_motor);
            sendPost('/api/menorah/state_update', { fish: { tail_motor: localState.fish.tail_motor } });
        });
    }

    if (btnFishSpotlight) {
        btnFishSpotlight.addEventListener('click', () => {
            localState.fish.head_spotlight = !localState.fish.head_spotlight;
            btnFishSpotlight.classList.toggle('active', localState.fish.head_spotlight);
            sendPost('/api/menorah/state_update', { fish: { head_spotlight: localState.fish.head_spotlight } });
        });
    }

    // Sliders for Robot Arm Joints
    function setupRange(id, valId, key) {
        const slider = document.getElementById(id);
        const valEl = document.getElementById(valId);
        if (!slider) return;

        slider.addEventListener('input', (e) => {
            const v = parseFloat(e.target.value);
            if (valEl) valEl.textContent = v + (key === 'j5_gripper' ? '%' : '°');
            localState.robot_arm[key] = v;
            sendPost('/api/menorah/state_update', { robot_arm: { [key]: v } });
        });
    }

    setupRange('armJ1', 'armJ1Val', 'j1_base');
    setupRange('armJ2', 'armJ2Val', 'j2_shoulder');
    setupRange('armJ3', 'armJ3Val', 'j3_elbow');
    setupRange('armJ4', 'armJ4Val', 'j4_wrist');
    setupRange('armJ5', 'armJ5Val', 'j5_gripper');

    // Turntable Base Slider & Toggle
    setupRange('baseAngle', 'baseAngleVal', 'servo_angle');
    const btnBaseRandom = document.getElementById('btnBaseRandom');
    if (btnBaseRandom) {
        btnBaseRandom.addEventListener('click', () => {
            localState.main_base.random_moving = !localState.main_base.random_moving;
            btnBaseRandom.classList.toggle('active', localState.main_base.random_moving);
            sendPost('/api/menorah/state_update', { main_base: { random_moving: localState.main_base.random_moving } });
        });
    }

    // --- CONTINUOUS CAMERA STREAM REFRESH (NON-BLOCKING) ---
    const camFeedEl = document.getElementById('camFeed');
    const camSourceSelect = document.getElementById('camSourceSelect');
    const btnResetCam = document.getElementById('btnResetCam');
    let camLoading = false;

    function refreshCameraFrame() {
        if (!camFeedEl || camLoading) return;
        camLoading = true;
        const img = new Image();
        img.onload = () => {
            camFeedEl.src = img.src;
            camLoading = false;
            setTimeout(refreshCameraFrame, 800);
        };
        img.onerror = () => {
            camLoading = false;
            setTimeout(refreshCameraFrame, 1500);
        };
        img.src = `/api/camera/frame?t=${Date.now()}`;
    }
    refreshCameraFrame();

    if (camSourceSelect) {
        camSourceSelect.addEventListener('change', (e) => {
            sendPost('/api/camera/select', { source: e.target.value });
        });
    }

    if (btnResetCam) {
        btnResetCam.addEventListener('click', () => {
            sendPost('/api/camera/reset', {});
            setTimeout(refreshCameraFrame, 300);
        });
    }

    // --- MP3 SONG PLAYLIST & REAL-TIME WEB AUDIO LIPSYNC ENGINE ---
    const songSelect = document.getElementById('songSelect');
    const fileUploadInput = document.getElementById('fileUploadInput');
    const btnSongPlay = document.getElementById('btnSongPlay');
    const btnSongPause = document.getElementById('btnSongPause');
    const btnSongStop = document.getElementById('btnSongStop');
    const songProgressBar = document.getElementById('songProgressBar');
    const currTimeText = document.getElementById('currTimeText');
    const durTimeText = document.getElementById('durTimeText');
    const lipsyncGainSlider = document.getElementById('lipsyncGainSlider');
    const lipsyncGainVal = document.getElementById('lipsyncGainVal');
    const songVolumeSlider = document.getElementById('songVolumeSlider');
    const songVolumeVal = document.getElementById('songVolumeVal');
    const tailPulseGainSlider = document.getElementById('tailPulseGainSlider');
    const tailPulseGainVal = document.getElementById('tailPulseGainVal');
    const lipsyncBandSelect = document.getElementById('lipsyncBandSelect');
    const lipsyncThreshSelect = document.getElementById('lipsyncThreshSelect');
    const lipsyncBadge = document.getElementById('lipsyncBadge');

    let mp3Audio = new Audio();
    mp3Audio.crossOrigin = "anonymous";
    let mp3AudioCtx = null;
    let mp3Analyser = null;
    let mp3SourceNode = null;
    let isLipsyncing = false;

    function formatTime(sec) {
        if (isNaN(sec)) return "00:00";
        const m = Math.floor(sec / 60);
        const s = Math.floor(sec % 60);
        return `${m < 10 ? '0' : ''}${m}:${s < 10 ? '0' : ''}${s}`;
    }

    function loadPlaylist() {
        fetch('/api/playlist')
            .then(r => r.json())
            .then(data => {
                if (!data.songs || !songSelect) return;
                songSelect.innerHTML = '<option value="">-- Choose Song --</option>';
                data.songs.forEach(song => {
                    const opt = document.createElement('option');
                    opt.value = song.url;
                    opt.textContent = song.title;
                    songSelect.appendChild(opt);
                });
            })
            .catch(e => console.log("Playlist load error:", e));
    }
    loadPlaylist();

    if (songSelect) {
        songSelect.addEventListener('change', () => {
            if (songSelect.value) {
                mp3Audio.src = songSelect.value;
                mp3Audio.load();
            }
        });
    }

    if (fileUploadInput) {
        fileUploadInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (!file) return;

            const reader = new FileReader();
            reader.onload = function(evt) {
                const b64 = evt.target.result.split(',')[1];
                fetch('/api/playlist/upload', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filename: file.name, file_b64: b64 })
                })
                .then(r => r.json())
                .then(res => {
                    if (res.url) {
                        loadPlaylist();
                        setTimeout(() => {
                            if (songSelect) songSelect.value = res.url;
                            mp3Audio.src = res.url;
                            mp3Audio.play();
                            startMp3Lipsync();
                        }, 400);
                    }
                });
            };
            reader.readAsDataURL(file);
        });
    }

    function initWebAudio() {
        if (!mp3AudioCtx) {
            mp3AudioCtx = new (window.AudioContext || window.webkitAudioContext)();
            mp3Analyser = mp3AudioCtx.createAnalyser();
            mp3Analyser.fftSize = 512;
            mp3SourceNode = mp3AudioCtx.createMediaElementSource(mp3Audio);
            mp3SourceNode.connect(mp3Analyser);
            mp3Analyser.connect(mp3AudioCtx.destination);
        }
        if (mp3AudioCtx.state === 'suspended') {
            mp3AudioCtx.resume();
        }
    }

    function startMp3Lipsync() {
        initWebAudio();
        isLipsyncing = true;
        if (lipsyncBadge) lipsyncBadge.textContent = "🎶 FISH SINGING & LIPSYNC ACTIVE";

        function analyzeLoop() {
            if (!isLipsyncing || mp3Audio.paused || mp3Audio.ended) {
                isLipsyncing = false;
                if (lipsyncBadge) lipsyncBadge.textContent = "🎶 Web Audio Lipsync Engine";
                sendPost('/api/playlist/lipsync_state', { is_singing: false, mouth_open: false, beat_pulse: false });
                return;
            }

            const dataArray = new Uint8Array(mp3Analyser.frequencyBinCount);
            mp3Analyser.getByteFrequencyData(dataArray);

            const bandMode = lipsyncBandSelect ? lipsyncBandSelect.value : 'vocal';
            let startBin = 10, endBin = 80;
            if (bandMode === 'bass') { startBin = 1; endBin = 12; }
            else if (bandMode === 'full') { startBin = 2; endBin = 180; }

            let vocalSum = 0;
            for (let i = startBin; i < endBin; i++) vocalSum += dataArray[i];
            let vocalAvg = vocalSum / (endBin - startBin);

            let bassSum = 0;
            for (let i = 1; i < 10; i++) bassSum += dataArray[i];
            let bassAvg = bassSum / 9;

            const gainVal = lipsyncGainSlider ? parseInt(lipsyncGainSlider.value) : 45;
            const threshVal = lipsyncThreshSelect ? parseInt(lipsyncThreshSelect.value) : 25;
            const tailGain = tailPulseGainSlider ? parseInt(tailPulseGainSlider.value) : 70;

            const isMouthOpen = (vocalAvg * (gainVal / 45.0)) > threshVal;
            const isBeatPulse = (bassAvg * (tailGain / 70.0)) > 130;

            sendPost('/api/playlist/lipsync_state', {
                is_singing: true,
                mouth_open: isMouthOpen,
                beat_pulse: isBeatPulse
            });

            requestAnimationFrame(analyzeLoop);
        }

        analyzeLoop();
    }

    if (btnSongPlay) {
        btnSongPlay.addEventListener('click', () => {
            if (!mp3Audio.src && songSelect && songSelect.value) {
                mp3Audio.src = songSelect.value;
            }
            if (mp3Audio.src) {
                mp3Audio.play();
                startMp3Lipsync();
            }
        });
    }

    if (btnSongPause) {
        btnSongPause.addEventListener('click', () => {
            mp3Audio.pause();
            isLipsyncing = false;
        });
    }

    if (btnSongStop) {
        btnSongStop.addEventListener('click', () => {
            mp3Audio.pause();
            mp3Audio.currentTime = 0;
            isLipsyncing = false;
        });
    }

    if (mp3Audio) {
        mp3Audio.addEventListener('timeupdate', () => {
            if (mp3Audio.duration) {
                const pct = (mp3Audio.currentTime / mp3Audio.duration) * 100;
                if (songProgressBar) songProgressBar.value = pct;
                if (currTimeText) currTimeText.textContent = formatTime(mp3Audio.currentTime);
                if (durTimeText) durTimeText.textContent = formatTime(mp3Audio.duration);
            }
        });
    }

    if (songProgressBar) {
        songProgressBar.addEventListener('input', (e) => {
            if (mp3Audio.duration) {
                mp3Audio.currentTime = (e.target.value / 100) * mp3Audio.duration;
            }
        });
    }

    if (songVolumeSlider && songVolumeVal) {
        songVolumeSlider.addEventListener('input', (e) => {
            const v = e.target.value;
            mp3Audio.volume = v / 100;
            songVolumeVal.textContent = v + '%';
        });
    }

    if (lipsyncGainSlider && lipsyncGainVal) {
        lipsyncGainSlider.addEventListener('input', (e) => {
            lipsyncGainVal.textContent = e.target.value + '%';
        });
    }

    if (tailPulseGainSlider && tailPulseGainVal) {
        tailPulseGainSlider.addEventListener('input', (e) => {
            tailPulseGainVal.textContent = e.target.value + '%';
        });
    }

    // --- 4. AI CHAT & SPEECH SYNTHESIZER ---
    const aiPromptInput = document.getElementById('aiPromptInput');
    const btnSendChat = document.getElementById('btnSendChat');
    const aiResponseBox = document.getElementById('aiResponseBox');

    function speakTextAndSyncFish(text) {
        if (!text) return;
        aiResponseBox.innerHTML = `<strong>🐟 MENORAH FISH:</strong> ${text}`;

        const audioUrl = `/api/tts/speak?text=${encodeURIComponent(text)}&voice=${encodeURIComponent(localState.active_voice)}`;
        const audio = new Audio(audioUrl);

        audio.onended = () => {
            sendPost('/api/menorah/state_update', { is_speaking: false });
        };

        sendPost('/api/menorah/state_update', { is_speaking: true });
        audio.play().catch(e => console.log("Audio play error:", e));
    }

    function sendChat() {
        const text = aiPromptInput.value.trim();
        if (!text) return;

        aiResponseBox.textContent = "Thinking & preparing Menorah Fish response...";
        fetch('/api/gemini/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt: text })
        })
        .then(r => r.json())
        .then(data => {
            aiPromptInput.value = '';
            if (data.text) {
                speakTextAndSyncFish(data.text);
            }
        })
        .catch(err => {
            aiResponseBox.textContent = "Error communicating with AI.";
        });
    }

    if (btnSendChat) btnSendChat.addEventListener('click', sendChat);
    if (aiPromptInput) aiPromptInput.addEventListener('keypress', e => { if (e.key === 'Enter') sendChat(); });

    // Download Python Script Button
    const btnExportCode = document.getElementById('btnExportCode');
    if (btnExportCode) {
        btnExportCode.addEventListener('click', () => {
            window.location.href = '/api/export-python';
        });
    }

    // Camera Stance Preset View Buttons
    const camBtnMap = [
        { id: 'btnCamViewDefault', view: 'default' },
        { id: 'btnCamViewTop', view: 'top' },
        { id: 'btnCamViewFish', view: 'fish' },
        { id: 'btnCamViewArm', view: 'arm' }
    ];

    camBtnMap.forEach(item => {
        const btn = document.getElementById(item.id);
        if (btn) {
            btn.addEventListener('click', () => {
                camBtnMap.forEach(b => { const el = document.getElementById(b.id); if (el) el.classList.remove('active'); });
                btn.classList.add('active');
                if (visualizer) visualizer.setCameraView(item.view);
            });
        }
    });

    // --- 5. STATE POLL & SYNC LOOP & TELEMETRY HUD UPDATE ---
    setInterval(() => {
        fetch('/api/menorah/state')
            .then(r => r.json())
            .then(data => {
                localState = data;
                if (visualizer) visualizer.updateState(data);

                // Update Menorah Status Line
                if (data.menorah && menorahStatusText) {
                    const count = data.menorah.lit_count || 0;
                    menorahStatusText.textContent = (count === 0) ? "Center Shamash + 0 Side Candles Lit" : `Center Shamash + ${count} Side Candles Lit`;
                }

                // Update Real-Time Telemetry HUD Elements
                const hudMouth = document.getElementById('hudMouthText');
                const hudNeck = document.getElementById('hudNeckText');
                const hudTail = document.getElementById('hudTailText');
                const hudArm = document.getElementById('hudArmText');
                const hudMenorah = document.getElementById('hudMenorahText');
                const hudDomes = document.getElementById('hudDomesText');

                if (data.fish) {
                    if (hudMouth) hudMouth.textContent = (data.fish.mouth_motor || data.is_speaking) ? "ACTIVE (L298 ChA Mouth Open)" : "IDLE (Mouth Closed)";
                    if (hudNeck) {
                        const neckPos = (data.fish.neck_position || 0.0).toFixed(2);
                        const pwm = data.fish.neck_motor_pwm || 0;
                        hudNeck.textContent = (data.fish.neck_position > 0.01) ? `SWINGING (${pwm}% PWM, ${neckPos} Pos)` : "0% PWM (0.0s Retracted)";
                    }
                    if (hudTail) hudTail.textContent = (data.fish.tail_motor || data.is_speaking) ? "WAGGING (L298 #2 ChA)" : "OFF (Idle Burst Mode)";
                }

                if (data.robot_arm && hudArm) {
                    const arm = data.robot_arm;
                    hudArm.textContent = `J1:${Math.round(arm.j1_base)}° | J2:${Math.round(arm.j2_shoulder)}° | J3:${Math.round(arm.j3_elbow)}° | Claw Candle: ON`;
                }

                if (data.menorah && hudMenorah) {
                    const cnt = data.menorah.lit_count || 0;
                    hudMenorah.textContent = `Center Shamash + ${cnt} Side Candles LIT`;
                }

                if (data.light_domes && hudDomes) {
                    const isBreathing = !!(data.light_domes.breathing || data.is_speaking);
                    hudDomes.textContent = isBreathing ? "Breathing Pulse Sequence" : "Steady 100% Illumination";
                }
            })
            .catch(() => {});
    }, 500);

    // --- 6. TAB NAVIGATION & CONFIGURATION SYSTEM ---
    function switchTab(targetTabId) {
        if (!targetTabId) return;

        document.querySelectorAll('.tab-pane').forEach(pane => pane.style.display = 'none');
        document.querySelectorAll('.nav-tab-btn').forEach(btn => btn.classList.remove('active'));

        const targetPane = document.getElementById(targetTabId);
        if (targetPane) targetPane.style.display = 'block';

        const matchingBtn = document.querySelector(`.nav-tab-btn[data-tab="${targetTabId}"]`);
        if (matchingBtn) matchingBtn.classList.add('active');

        if (targetTabId === 'tabWiring') {
            initWiringDiagramEngine();
        } else if (targetTabId === 'tabConfig') {
            populateMediaDevices();
        }
    }
    window.switchTab = switchTab;

    document.querySelectorAll('.nav-tab-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const tabId = btn.getAttribute('data-tab');
            switchTab(tabId);
        });
    });

    // Populate Media Devices
    const configMicSelect = document.getElementById('configMicSelect');
    const configAudioOutputSelect = document.getElementById('configAudioOutputSelect');

    async function populateMediaDevices() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return;
        try {
            await navigator.mediaDevices.getUserMedia({ audio: true }).catch(() => {});
            const devices = await navigator.mediaDevices.enumerateDevices();

            if (configMicSelect) {
                configMicSelect.innerHTML = '<option value="default">Default System Microphone</option>';
                devices.filter(d => d.kind === 'audioinput').forEach((dev, idx) => {
                    const opt = document.createElement('option');
                    opt.value = dev.deviceId;
                    opt.textContent = dev.label || `Microphone ${idx + 1}`;
                    configMicSelect.appendChild(opt);
                });
            }
        } catch (e) {}
    }

    // --- 7. SERVO CALIBRATION & HARDWARE OUTPUT DIAGNOSTICS ---
    function adjustOffset(inputId, delta) {
        const slider = document.getElementById(inputId);
        if (!slider) return;
        let curr = parseInt(slider.value) || 0;
        let nextVal = Math.min(30, Math.max(-30, curr + delta));
        slider.value = nextVal;
        slider.dispatchEvent(new Event('input'));
    }
    window.adjustOffset = adjustOffset;

    function setupCalibOffset(id, valId, label) {
        const slider = document.getElementById(id);
        const valEl = document.getElementById(valId);
        if (slider && valEl) {
            slider.addEventListener('input', (e) => {
                const v = parseInt(e.target.value);
                valEl.textContent = (v > 0 ? '+' : '') + v + '°';
            });
        }
    }

    const calibOffsetIds = [
        { id: 'calibArmJ1Offset', valId: 'calibArmJ1OffsetVal', label: 'Arm Base (J1 Ch 0)' },
        { id: 'calibArmJ2Offset', valId: 'calibArmJ2OffsetVal', label: 'Arm Shoulder (J2 Ch 1)' },
        { id: 'calibArmJ3Offset', valId: 'calibArmJ3OffsetVal', label: 'Arm Elbow (J3 Ch 2)' },
        { id: 'calibArmJ4Offset', valId: 'calibArmJ4OffsetVal', label: 'Arm Wrist (J4 Ch 5)' },
        { id: 'calibArmJ5Offset', valId: 'calibArmJ5OffsetVal', label: 'Arm Gripper (J5)' },
        { id: 'calibMouthServoOffset', valId: 'calibMouthServoOffsetVal', label: 'Mouth Servo (Ch 3)' },
        { id: 'calibTailServoOffset', valId: 'calibTailServoOffsetVal', label: 'Tail Servo (Ch 4)' },
        { id: 'calibFishSpotPanOffset', valId: 'calibFishSpotPanOffsetVal', label: 'Fish Spot Pan (Ch 9)' },
        { id: 'calibFishSpotTiltOffset', valId: 'calibFishSpotTiltOffsetVal', label: 'Fish Spot Tilt (Ch 10)' },
        { id: 'calibLeftSpotPanOffset', valId: 'calibLeftSpotPanOffsetVal', label: 'Left Dreidel Spot Pan (Ch 12)' },
        { id: 'calibRightSpotPanOffset', valId: 'calibRightSpotPanOffsetVal', label: 'Right Dreidel Spot Pan (Ch 13)' }
    ];

    calibOffsetIds.forEach(item => {
        setupCalibOffset(item.id, item.valId, item.label);
    });

    function saveServoOffsets() {
        const offsets = {};
        calibOffsetIds.forEach(item => {
            const el = document.getElementById(item.id);
            if (el) offsets[item.id] = parseInt(el.value);
        });
        localStorage.setItem('menorahfish_servo_offsets', JSON.stringify(offsets));
        sendPost('/api/menorah/state_update', { servo_offsets: offsets });
        alert("💾 Saved all servo calibration trim offsets to system memory!");
    }

    function loadSavedServoOffsets() {
        try {
            const saved = localStorage.getItem('menorahfish_servo_offsets');
            if (!saved) return;
            const offsets = JSON.parse(saved);
            calibOffsetIds.forEach(item => {
                if (offsets[item.id] !== undefined) {
                    const el = document.getElementById(item.id);
                    const valEl = document.getElementById(item.valId);
                    if (el) el.value = offsets[item.id];
                    if (valEl) valEl.textContent = (offsets[item.id] > 0 ? '+' : '') + offsets[item.id] + '°';
                }
            });
        } catch (e) {}
    }

    function resetServoOffsets() {
        calibOffsetIds.forEach(item => {
            const el = document.getElementById(item.id);
            const valEl = document.getElementById(item.valId);
            if (el) el.value = 0;
            if (valEl) valEl.textContent = '0°';
        });
        saveServoOffsets();
    }

    const btnSaveCalibOffsets = document.getElementById('btnSaveCalibOffsets');
    if (btnSaveCalibOffsets) btnSaveCalibOffsets.addEventListener('click', saveServoOffsets);

    const btnResetCalibOffsets = document.getElementById('btnResetCalibOffsets');
    if (btnResetCalibOffsets) btnResetCalibOffsets.addEventListener('click', resetServoOffsets);

    loadSavedServoOffsets();

    // --- 8. WIRING DIAGRAM & PINOUT ENGINE ---
    const pinoutConnectionsData = [
        { module: "Raspberry Pi", pin: "Pin 3", signal: "GPIO 2 (SDA1)", color: "Cyan", hex: "#00f0ff", target: "PCA9685 PWM Driver", term: "SDA Terminal", desc: "I2C Serial Data Bus for 16-Channel Servo Controller" },
        { module: "Raspberry Pi", pin: "Pin 5", signal: "GPIO 3 (SCL1)", color: "Blue", hex: "#3399ff", target: "PCA9685 PWM Driver", term: "SCL Terminal", desc: "I2C Serial Clock Bus for 16-Channel Servo Controller" },
        { module: "Raspberry Pi", pin: "Pin 12", signal: "GPIO 18 (PWM)", color: "Magenta", hex: "#ff00cc", target: "L298N Driver #1", term: "ENA Terminal", desc: "Fish Mouth DC Motor Speed PWM" },
        { module: "Raspberry Pi", pin: "Pin 35", signal: "GPIO 19 (PWM)", color: "Magenta", hex: "#ff00cc", target: "L298N Driver #1", term: "ENB Terminal", desc: "Fish Neck 3s Gradual Outstretched Swing PWM" },
        { module: "Raspberry Pi", pin: "Pin 32", signal: "GPIO 12 (PWM)", color: "Cyan", hex: "#00f0ff", target: "L298N Driver #2", term: "ENA Terminal", desc: "Fish Tail Wagging Motor Speed PWM" },
        { module: "PCA9685 PWM", pin: "Channel 0", signal: "PWM Servo Out", color: "Red", hex: "#ff3344", target: "Robot Arm J1", term: "Base Yaw Servo", desc: "Robot Arm Base Rotation (-90° to +90°)" },
        { module: "PCA9685 PWM", pin: "Channel 1", signal: "PWM Servo Out", color: "Red", hex: "#ff3344", target: "Robot Arm J2", term: "Shoulder Servo", desc: "Robot Arm Shoulder Pitch (-90° to +90°)" },
        { module: "PCA9685 PWM", pin: "Channel 2", signal: "PWM Servo Out", color: "Red", hex: "#ff3344", target: "Robot Arm J3", term: "Elbow Servo", desc: "Robot Arm Elbow Pitch (-135° to +135°)" },
        { module: "PCA9685 PWM", pin: "Channel 3", signal: "PWM Servo Out", color: "Gold", hex: "#ffd700", target: "Stage Servo 1", term: "Mouth-Side Servo", desc: "Mouth-Side Stage Servo (Sweeps during speech)" },
        { module: "PCA9685 PWM", pin: "Channel 4", signal: "PWM Servo Out", color: "Gold", hex: "#ffd700", target: "Stage Servo 2", term: "Tail-Side Servo", desc: "Tail-Side Stage Servo (Sweeps during speech)" },
        { module: "PCA9685 PWM", pin: "Channel 5", signal: "PWM Servo Out", color: "Magenta", hex: "#ff00cc", target: "Robot Arm J4/J5", term: "Wrist/Claw Servo", desc: "Robot Arm Wrist & Gripper Candle Claw" },
        { module: "PCA9685 PWM", pin: "Channel 15", signal: "PWM Servo Out", color: "Purple", hex: "#a855f7", target: "Turntable Base", term: "Base Servo Motor", desc: "Main Stage Rotating Turntable Servo Drive" }
    ];

    let wiringEngineInitialized = false;

    function renderPinoutTable() {
        const tbody = document.getElementById('pinoutTableBody');
        if (!tbody) return;

        tbody.innerHTML = '';
        pinoutConnectionsData.forEach(item => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong style="color:var(--text-main);">${item.module}</strong></td>
                <td><span class="color-pill" style="background: rgba(255,255,255,0.06); color: ${item.hex}; border: 1px solid ${item.hex};">${item.pin}</span></td>
                <td><code style="color:var(--accent-cyan); font-weight:bold;">${item.signal}</code></td>
                <td><span class="color-pill" style="background: rgba(0,0,0,0.3); color: ${item.hex};"><span class="color-dot" style="background:${item.hex};"></span>${item.color}</span></td>
                <td><strong style="color:var(--text-main);">${item.target}</strong></td>
                <td><code style="color:var(--accent-yellow);">${item.term}</code></td>
                <td style="font-size:0.8rem; color:var(--text-muted);">${item.desc}</td>
            `;
            tbody.appendChild(tr);
        });
    }

    function initWiringDiagramEngine() {
        if (wiringEngineInitialized) return;
        wiringEngineInitialized = true;
        renderPinoutTable();

        const btnDownloadPdf = document.getElementById('btnDownloadPdf');
        if (btnDownloadPdf) {
            btnDownloadPdf.addEventListener('click', () => {
                window.location.href = '/api/export-pdf';
            });
        }

        const btnDownloadCsv = document.getElementById('btnDownloadCsv');
        if (btnDownloadCsv) {
            btnDownloadCsv.addEventListener('click', () => {
                window.location.href = '/api/export-csv';
            });
        }

        const btnDownloadSvg = document.getElementById('btnDownloadSvg');
        if (btnDownloadSvg) {
            btnDownloadSvg.addEventListener('click', () => {
                window.location.href = '/wiring_diagram.svg';
            });
        }
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', startApp);
} else {
    startApp();
}
