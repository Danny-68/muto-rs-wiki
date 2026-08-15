# 🔄 Overdracht — lees dit eerst in een nieuwe sessie

**Laatst bijgewerkt:** 15 augustus 2026 (avond, na de karakteriseringssessie)
**Volledige details:** [docs/ROADMAP.md](docs/ROADMAP.md) secties "🎯 Planningssessie 15 augustus 2026" en "✅ Uitvoering 15 augustus 2026"

---

## Waar we nu staan (in één alinea)

De externe ICM20948 is opnieuw aangesloten en werkt weer (magnetometer-timeout weg, `/imu` stabiel op 20Hz). `ekf_params.yaml` (Pad A) stond in de container al onveranderd correct. Een nieuw testscript ([`combi_calibration_test.py`](combi_calibration_test.py)) is gebouwd en gedraaid over vijf fases: stationary, STM32-Hz-bus-contentie, afstandskalibratie vooruit/achteruit, rotatiekalibratie, en een gecombineerde manoeuvre. **Belangrijkste bevinding: de externe IMU is bij actieve rotatie in BEIDE richtingen onbetrouwbaar** (niet alleen linksom, zoals de 14-augustus-overdracht meldde) — root cause voorlopig gevonden en omzeild via `MAG_GAIN=0.0` in `imu_publisher.py` (magnetometer-correctie uit, zuivere gyro-integratie). Dat is bevestigd in beide rotatierichtingen én tijdens een complexere gecombineerde manoeuvre (180°-draai + vooruit + kleine draai, alle drie sensoren binnen ~4° van elkaar).

**⚠️ Dit is een workaround, geen fix.** Zonder magnetometer-correctie is er geen absolute-heading-referentie meer — puur gyro-integratie zal over langere missies wegdrijven. De onderliggende as-remap-bug (nooit geverifieerd, al gevlagd in `imu_publisher.py`'s eigen docstring) is nog niet root-oorzakelijk gevonden.

---

## Direct te doen, in deze volgorde

1. **Bevestig dat `MAG_GAIN=0.0` nog steeds staat** in `imu_publisher.py` (zowel host `/home/pi/` als container `/root/`) — dit is een bewuste, tijdelijke keuze, geen abusievelijke wijziging. Backup van de originele waarde (0,01): `imu_publisher.py.bak_20260815_maggaintest`.
2. **As-remap-root-cause onderzoeken** (nu dat de workaround bevestigd werkt, is dit niet meer urgent-blokkerend, maar wel nog open): magnetometer-as-remap in `imu_publisher.py` verifiëren tegen het ICM20948-datasheet (Figuur 12/13), zoals de docstring zelf al aangeeft nooit gedaan te zijn. Doel: magnetometer-correctie weer veilig aan kunnen zetten, zodat langetermijn-yaw-drift weer gecorrigeerd wordt.
3. **`robot_bridge.py`'s `SPEED_TABLE`/`STEP_DISTANCE_M` nog steeds niet vernieuwd** — de vandaag gedane afstandskalibratie (bevestigde `MAX_LINEAR_SPEED_MPS` in `phoenix_driver.py`) geldt voor een ander bewegingspad (`phoenix_gait.py`/Nav2), niet voor de STM32-firmware-gait die `robot_bridge.py`/Dify/spraak gebruikt. Als dat pad ook gebruikt wordt, moet het apart gekalibreerd worden met dezelfde methode.
4. **RF2O x/y-correctiefactor overwegen (~1,068×)** — RF2O onderschat consistent ~6-7% in beide richtingen (n=2, dus nog een voorlopig signaal, meer reps zouden dit steviger maken). In tegenstelling tot yaw (teken-wisselende fout, niet met vaste factor te repareren) lijkt dit wél met een vaste schaalcorrectie op te lossen.
5. **Residual-gate-node en stop-and-correct-navigatielus nog niet gebouwd** — vandaag leverde alleen de karakteriseringsdata die daarvoor nodig is (zie ROADMAP.md A/C).
6. **STM32-Hz-bus-contentie blijft bestaan, ook bij de huidige 2Hz-instelling** (+87,8% wall-clock-overhead, gemeten en bevestigd) — geen actie ondernomen, alleen gekwantificeerd. Plafond op ~3,4Hz werkelijk haalbare rate, ongeacht gevraagde rate.
7. **180°-laser-TF-fix blijft elke sessie checken** (container-lokale `sed`-aanpassing, niet persistent) — ongewijzigd advies uit eerdere sessies.

---

## Openstaande bugs (nog niet gefixt)

- **Nav2 `NavigateToPose` liep veel verder dan het doel** (30cm werd >50cm, 17 recoveries, 14 aug) — root cause nog onbekend, nog te onderzoeken via `/tmp/nav2.log` en de costmap-configuratie. Vandaag niet aangeraakt.
- **`phoenix_driver.py` kan stil crashen** (geen traceback/OOM/USB-disconnect zichtbaar, 14 aug) — reden onbekend. Vandaag niet aangeraakt, blijft open.
- **As-remap-bug in `imu_publisher.py`'s magnetometer-fusie** (nieuw vandaag) — root cause nog niet gevonden, alleen omzeild via `MAG_GAIN=0.0`. Zie "Direct te doen" punt 2.

---

## Bewust uitgesteld (lagere prioriteit, met reden)

- **Zijwaartse drift tijdens recht-vooruit-lopen** — ongewijzigd, nog niet herzien.
- **Pad B (zachte gait-variant)** — on hold, ongewijzigd.
- **Astra Pro Plus + ICP-pointcloud-odometrie** — blijft geparkeerd. Vandaag is bovendien gebleken dat RF2O x/y met een simpele schaalcorrectie waarschijnlijk goed genoeg is (~6-7% consistente onderschatting, geen chaotische fout) — nog minder reden om een extra sensor toe te voegen dan eerder gedacht.

---

## Belangrijke, blijvende lessen uit deze sessie (15 augustus 2026)

- **Een aanname over "we gebruiken de magnetometer niet" bleek onjuist te zijn tot we de code echt narekenden** — `MAG_GAIN` stond op 0,01 (klein maar niet nul). De 11-augustus-fix voor magnetometerinterferentie was fysiek (IMU verplaatst), nooit software-matig (`MAG_GAIN` is toen niet aangepast). Twee verschillende fixes voor mogelijk hetzelfde soort probleem, niet met elkaar verward moeten worden — check de code, vertrouw niet op wat je denkt dat er nog staat.
- **Een yaw-representatie begrensd tot ±180° vereist een wrap-gecorrigeerde aftrekking voor elke delta-berekening** — een kale `after - before` gaf een keer -304,98° i.p.v. de werkelijke +55,02°. Geldt voor élke hoekmeting in dit project, niet alleen deze ene test.
- **Bij een polling-loop die "elke N seconden iets doet" tijdens een tijd-kritische lus: plan het volgende moment altijd relatief aan nu (`time.monotonic() + interval`), nooit cumulatief vanaf een vast schema (`volgende += interval`)** — bij de laatste blijft de klok voorgoed achterlopen zodra één iteratie langer duurt dan het interval, met een op-hol-geslagen lus tot gevolg.
- **Consistente, richtingsonafhankelijke fouten (RF2O-onderschatting) zijn met een vaste factor te repareren; teken-wisselende/richtingsafhankelijke fouten (yaw bij oude rf2o, nu ook de externe-IMU-rotatiebug) meestal niet** — dat onderscheid bepaalt of "gewoon een correctiefactor toepassen" een zinnige aanpak is.
- **Fysieke plaatsing verifiëren vóórdat je een probleem aan interferentie toeschrijft** — de gebruiker bevestigde dat de externe IMU al in de verhoogde/geïsoleerde positie zat, wat de eerdere "waarschijnlijk hetzelfde oude interferentieprobleem"-hypothese minder aannemelijk maakte en de softwarebug-hypothese sterker.
- (Blijft gelden, uit eerdere sessies) **Nooit een lange, blinde rotatieduur commanderen** op basis van een niet-gevalideerde snelheid; **wachttijden altijd met `time.sleep()`**; **minimaal ~24-27 seconden wachten na elke stop** voor een betrouwbare yaw/pose-meting; **code op de Pi-host kan afwijken van wat er in de container draait — altijd de container-kopie checken** (bevestigd nogmaals vandaag bij de EKF-config-check).
