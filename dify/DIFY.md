# 🤖 Dify & LLM Controle — Yahboom Muto RS

---

## Architectuur Overzicht

```
Gebruiker (Dify Studio)
    │
    ▼
Dify Workflow (localhost/apps)
    │
    ├── Decision LLM (llama.cpp / Qwen2.5-14B)
    │   └── Bepaalt: is dit uitvoerbaar? Welke stappen?
    │
    ├── CODE_PARSEN
    │   └── Parseert JSON stappen array
    │
    ├── IF/ELSE (executable == true)
    │   │
    │   ├── TRUE: Iteration → Execution LLM → HTTP POST
    │   │         └── POST http://192.168.68.88:8080/execute_commands
    │   │
    │   └── FALSE: reason_output (uitleg waarom niet uitvoerbaar)
    │
    └── result_parser → End
```

**Waarom twee-staps LLM (niet ReAct agent):**
- qwen2.5:14b maakt JSON syntax fouten bij geneste quoting in ReAct action_input
- Twee-staps workflow: elke LLM produceert slechts één platte JSON laag → betrouwbaar

---

## Werkende Workflow: "Muto RS Controller (Yahboom stack)"

### Node configuratie

| Node | Type | Beschrijving |
|---|---|---|
| Start | Input | Gebruikersvraag |
| Decision LLM | LLM | qwen2.5:14b, bepaalt executable + steps |
| CODE_PARSEN | Code | Parseert JSON steps array |
| IF/ELSE | Conditie | `code_parsen.executable is true` |
| Iteration | Iteratie | Over steps array |
| Execution LLM | LLM | Schrijft flat command-JSON |
| HTTP POST | HTTP | POST naar Pi :8080/execute_commands |
| result_parser | Code | Verwerkt API response |
| reason_output | Output | **NAAM IS BELANGRIJK** (niet "result" → duplicate variable fout) |
| End | Output | Eindresultaat |

### HTTP POST instelling
```
URL:     http://192.168.68.88:8080/execute_commands
Method:  POST
Headers: Content-Type: application/json
```

### ELSE branch output node
> ⚠️ De output node in de ELSE branch MOET `reason_output` heten, NIET `result`.
> Anders: "duplicate variable error"

---

## llama.cpp Backend

### Configuratie in Dify
- Plugin: OpenAI-API-compatible
- Endpoint: `http://192.168.68.77:8081/v1`
- Model alias: `qwen2.5-14b-instruct`

### llama.cpp server starten
```
D:\llama.cpp\start_llama.bat
```

### Verificatie
```powershell
# 🪟 WINDOWS POWERSHELL
Invoke-RestMethod -Uri "http://localhost:8081/v1/models" | ConvertTo-Json
```

---

## Dify Omgevingsvariabelen

Instellen in Dify workflow als Environment Variables:

| Variabele | Bron |
|---|---|
| `ability` | `/root/muto-llm-2.0/muto-llm-2.0/prompt_backup_en/env/` |
| `ability_function_name` | Zelfde map |
| `Examples` | Zelfde map |

---

## Dify Installatie & Beheer

### Locatie
```
D:\dify\docker\
```

> ⚠️ NOOIT `C:\WINDOWS\system32\dify` — wordt bij wijzigen ook verwijzend naar die pad

### Opstarten
```powershell
# 🪟 WINDOWS POWERSHELL
cd D:\dify\docker
docker compose up -d
```

### 502 Bad Gateway fix
```powershell
docker compose restart nginx
# Wacht ~10 seconden, refresh http://localhost/apps
```

### SSRF fix (vereist voor Pi toegang)
Voeg toe aan `D:\dify\docker\.env`:
```env
SSRF_PROXY_ALLOW_PRIVATE_IPS=192.168.68.88
```

### Schema update procedure
Na wijziging van OpenAPI schema:
1. Sla schema op in Dify tool
2. **Klik "Configure" knop** in de Tool List node
3. Zonder dit: Dify blijft de oude definitie gebruiken

---

## have_a_look() — Camera + Vision

### Werking
1. Snapshot van `/camera/color/image_raw`
2. Upload naar Dify Files API
3. Voer Dify vision workflow uit
4. Antwoord terug als tekst

### Aanroep via API
```json
{
  "status": "success",
  "plan": [
    {"id": "1", "command": "have_a_look(user_query='Wat zie je voor je?')"}
  ]
}
```

### Beschikbare parameters
```python
have_a_look(
    user_query="Beschrijf de omgeving",
    # of ook: query, question, description
)
```

---

## Direct API Test (zonder Dify)

```bash
# 🐧 PI TERMINAL — motor test
curl -s -X POST http://localhost:8080/execute_commands \
  -H "Content-Type: application/json" \
  -d '{
    "status": "success",
    "plan": [
      {"id": "1", "command": "forward(speed=15, duration=2)"},
      {"id": "2", "command": "stop()"}
    ]
  }' | python3 -m json.tool

# Camera test
curl -s -X POST http://localhost:8080/execute_commands \
  -H "Content-Type: application/json" \
  -d '{
    "status": "success",
    "plan": [
      {"id": "1", "command": "have_a_look()"}
    ]
  }' | python3 -m json.tool
```

---

## Probleemoplossing Dify

| Probleem | Oplossing |
|---|---|
| 502 Bad Gateway | `docker compose restart nginx` in `D:\dify\docker` |
| SSRF geblokkeerd | `SSRF_PROXY_ALLOW_PRIVATE_IPS=192.168.68.88` in `.env` |
| Schema niet bijgewerkt | Klik "Configure" knop in Tool List |
| Dify Studio niet bereikbaar | Gebruik `http://localhost/apps` (niet 192.168.68.77) |
| LLM geeft JSON fouten | Gebruik twee-staps workflow, geen ReAct agent |
| llama.cpp twee instanties | `taskkill /PID [pid] /F` voor beide PIDs |
