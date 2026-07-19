# 🪟 Windows PC — From Scratch Setup

Volledige instructie voor de Windows PC als Dify/LLM backend.

**Vaste IP:** `192.168.68.77`  
**GPU:** RTX 5080 (16GB VRAM)

---

## Stap 1 — Vereisten

- Windows 11 64-bit
- Docker Desktop met WSL2 backend
- Git for Windows
- NVIDIA driver + CUDA 13.3+

---

## Stap 2 — Docker Desktop

Download: https://www.docker.com/products/docker-desktop/

Instellingen na installatie:
- WSL2 backend inschakelen
- Minimaal 8GB RAM toewijzen aan Docker
- Resources → Shared drives: D:\ inschakelen

---

## Stap 3 — Dify installatie

```powershell
# Maak map op D schijf (NOOIT op C:\Windows\system32!)
mkdir D:\dify\docker
cd D:\dify\docker

# Clone Dify
git clone https://github.com/langgenius/dify.git .
cd docker

# Kopieer env (ZONDER /COPYALL flag!)
copy .env.example .env
```

### Kritieke .env aanpassingen

Open `D:\dify\docker\.env` en voeg toe/wijzig:
```env
SSRF_PROXY_ALLOW_PRIVATE_IPS=192.168.68.88
```

### Opstarten
```powershell
cd D:\dify\docker
docker compose up -d
```

**Wacht 60 seconden**, dan: http://localhost/apps

### Na updates of restart: nginx fix
```powershell
docker compose restart nginx
# Wacht 10 seconden, dan refreshen
```

---

## Stap 4 — llama.cpp installatie

### Downloaden
```powershell
mkdir D:\llama.cpp
cd D:\llama.cpp

# Download pre-built binary met CUDA support
# Van: https://github.com/ggerganov/llama.cpp/releases
# Kies: llama-b{buildnr}-bin-win-cuda-cu12.x-x64.zip
# Getest werkende build: b10064 met CUDA 13.3
```

### Model downloaden
```powershell
mkdir D:\llama.cpp\models
# Download Qwen2.5-14B-Instruct-Q4_K_M.gguf (~9GB)
# Van: https://huggingface.co/Qwen/Qwen2.5-14B-Instruct-GGUF
```

### Opstartscript aanmaken

Sla op als `D:\llama.cpp\start_llama.bat`:
```bat
@echo off
title LlamaServer - Qwen2.5-14B
color 0A
cd /d D:\llama.cpp

tasklist /FI "IMAGENAME eq llama-server.exe" 2>NUL | find /I "llama-server.exe" >NUL
if %ERRORLEVEL% == 0 (
    echo [WAARSCHUWING] llama-server.exe draait al!
    choice /C JN /M "Herstarten"
    if errorlevel 2 goto :EOF
    taskkill /F /IM llama-server.exe >NUL 2>&1
    timeout /t 2 /nobreak >NUL
)

D:\llama.cpp\llama-server.exe ^
    --model "D:\llama.cpp\models\Qwen2.5-14B-Instruct-Q4_K_M.gguf" ^
    --host 0.0.0.0 ^
    --port 8081 ^
    --n-gpu-layers 99 ^
    --ctx-size 8192 ^
    --batch-size 512 ^
    --ubatch-size 512 ^
    --threads 8 ^
    --parallel 2 ^
    --flash-attn on ^
    --alias "qwen2.5-14b-instruct"
pause
```

**Shortcut aanmaken:** klik rechts op `start_llama.bat` → Snelkoppeling maken → naar bureaublad.

### Specificaties bij RTX 5080
- VRAM gebruik: ~11.4 GB van 16 GB
- Snelheid: ~97 tokens/sec
- Context per slot: 4096 tokens (8192 / 2 parallel slots)

---

## Stap 5 — Dify koppelen aan llama.cpp

In Dify Studio (http://localhost/apps):

1. Settings → Model Providers → Add Provider
2. Kies: **OpenAI-API-compatible**
3. Vul in:
   - API Base: `http://192.168.68.77:8081/v1`
   - API Key: (willekeurig, bijv. `dummy`)
   - Model name: `qwen2.5-14b-instruct`
4. Sla op en test

---

## Stap 6 — Dify workflow importeren

In Dify Studio:
1. Create App → Import DSL
2. Importeer de workflow DSL uit het project
3. Stel HTTP node in: `http://192.168.68.88:8080/execute_commands`
4. Test met: "Loop 2 seconden vooruit"

---

## Verificatie

```powershell
# llama.cpp bereikbaar?
Invoke-RestMethod -Uri "http://localhost:8081/v1/models" | ConvertTo-Json

# Dify bereikbaar?
Start-Process "http://localhost/apps"

# Pi bereikbaar vanuit Dify Docker?
docker exec -it $(docker ps -q -f name=api) curl http://192.168.68.88:8080/health
```

---

## Dagelijks gebruik

1. Start Docker Desktop (automatisch bij Windows start)
2. Dubbelklik `D:\llama.cpp\start_llama.bat` (of snelkoppeling)
3. Wacht ~15 seconden tot model geladen is
4. Open http://localhost/apps
