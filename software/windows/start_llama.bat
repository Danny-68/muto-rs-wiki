@echo off
title LlamaServer - Qwen2.5-14B
color 0A
cd /d D:\llama.cpp

echo ========================================
echo  LlamaServer starten - Qwen2.5-14B
echo ========================================
echo.

tasklist /FI "IMAGENAME eq llama-server.exe" 2>NUL | find /I "llama-server.exe" >NUL
if %ERRORLEVEL% == 0 (
    echo [WAARSCHUWING] llama-server.exe draait al!
    choice /C JN /M "Herstarten"
    if errorlevel 2 goto :EOF
    taskkill /F /IM llama-server.exe >NUL 2>&1
    timeout /t 2 /nobreak >NUL
)

if not exist "D:\llama.cpp\models\Qwen2.5-14B-Instruct-Q4_K_M.gguf" (
    echo [FOUT] Model niet gevonden
    pause & exit /b 1
)

echo Model gevonden. Server starten...
echo Endpoint: http://0.0.0.0:8081/v1
echo VRAM: ~11.4 GB / 16 GB  ^|  ~97 tokens/sec
echo.

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

echo.
echo [INFO] Server gestopt.
pause
