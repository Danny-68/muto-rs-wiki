# ⏪ Rollback — teruggaan naar een eerdere staat

Deze repo is een **spiegel** van de live bestanden op de Pi, in `humble_run`/`muto_yahboom` (containers) en op de Jetson (`tools/upload.py` synct ze via de GitHub API). Omdat het gewoon een git-repo is, is de commit/tag-geschiedenis meteen je rollback-mechanisme — je hoeft nergens apart een back-up van bij te houden.

---

## Checkpoints (tags)

| Tag | Betekenis |
|---|---|
| `checkpoint-2026-08-09-voor-navigatie-update` | Laatste stand vóór de update van 9 augustus 2026 — komt overeen met de laatste `upload.py`-sync van 22 juli 2026, dus **vóór** alle Nav2-livedebug-fixes (30-31 juli, 7-9 augustus). |

Nieuwe checkpoints toevoegen (aanbevolen: vlak vóór elke `upload.py`-run):
```bash
cd muto-rs-wiki
git tag -a checkpoint-$(date +%Y%m%d) -m "omschrijving van de staat op dit moment"
git push origin checkpoint-$(date +%Y%m%d)
```

Overzicht van alle checkpoints:
```bash
git tag -l
git log --oneline --decorate  # tags zichtbaar naast de commits
```

---

## Eén bestand terugzetten naar een eerdere versie

**1. Bekijk wat er veranderd is sinds een checkpoint:**
```bash
git diff checkpoint-2026-08-09-voor-navigatie-update -- software/pi/ros2/robot_bridge.py
```

**2. Herstel die oude versie lokaal in de repo-clone:**
```bash
git checkout checkpoint-2026-08-09-voor-navigatie-update -- software/pi/ros2/robot_bridge.py
```

**3. Zet 'm terug op de live Pi/container/Jetson** (kies het juiste doelpad — zie `tools/upload.py` voor de volledige `GITHUB-pad → live-pad`-mapping):
```bash
# Pi host-bestand:
git show checkpoint-2026-08-09-voor-navigatie-update:software/pi/ros2/robot_bridge.py > /home/pi/robot_bridge.py

# Bestand in de humble_run container:
git show checkpoint-2026-08-09-voor-navigatie-update:software/container/config/hexapod_nav_params.yaml \
  | docker exec -i humble_run tee /root/hexapod_nav_params_custom.yaml > /dev/null

# Bestand op de Jetson (via SSH):
git show checkpoint-2026-08-09-voor-navigatie-update:software/jetson/scripts/muto_jetson_start.sh \
  | ssh Danny@192.168.68.86 "cat > /home/Danny/muto_jetson_start.sh"
```

**4. Herstart het bijbehorende proces** (bijv. `robot_bridge.py` opnieuw starten, of `docker restart humble_run` — zie [PROBLEMS.md](problems/PROBLEMS.md) voor per-component herstart-instructies).

---

## Volledige rollback (alle bestanden terug naar een checkpoint)

```bash
git checkout checkpoint-2026-08-09-voor-navigatie-update -- .
git commit -m "Rollback naar checkpoint-2026-08-09-voor-navigatie-update"
git push
```

Let op: dit verandert alleen de **repo**. Je moet de betrokken live-bestanden nog steeds handmatig terugzetten (stap 3 hierboven) — de repo is een spiegel, geen automatisch gesynchroniseerd systeem.

---

## Losstaande `.bak`-bestanden op de Pi zelf

Naast git-tags bestaan er op de Pi ook losse `.bak*`-kopieën die tijdens live-debugsessies zijn gemaakt vóór risicovolle wijzigingen (bijv. `hexapod_nav_params_custom.yaml.bak5_<timestamp>`, `muto_rtabmap_start.sh.bak_z0fix`, `muto_driver_fixed.py.bak_20260725_imutopic`). Die zijn NIET in deze repo gesynchroniseerd (upload.py leest alleen de "actuele" paden) — check bij twijfel eerst `ls -la` in `/home/pi/` naar `*.bak*`-bestanden voordat je een git-rollback probeert, soms is de snelste weg terug gewoon die lokale `.bak`-kopie.
