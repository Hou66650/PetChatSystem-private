param([string]$Python = "python")
$ErrorActionPreference = "Stop"
# webrtcvad-wheels supplies the same import without requiring Visual C++ on Windows.
& $Python -m pip install "numpy>=1.26,<3" "scipy>=1.10" "librosa>=0.10" "torch>=2.0" "typing" "webrtcvad-wheels==2.0.14.post1"
if ($LASTEXITCODE -ne 0) { throw "Voiceprint dependencies installation failed" }
& $Python -m pip install --no-deps "resemblyzer==0.1.4"
if ($LASTEXITCODE -ne 0) { throw "Voiceprint model installation failed" }
& $Python -c "from resemblyzer import VoiceEncoder; VoiceEncoder(device='cpu', verbose=False); print('Voiceprint model ready')"
if ($LASTEXITCODE -ne 0) { throw "Voiceprint model check failed" }
