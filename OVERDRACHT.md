# 🔄 Overdracht — lees dit eerst in een nieuwe sessie

**Laatst bijgewerkt:** 15 augustus 2026 (avond, sessie afgesloten)
**Volledige details:** [docs/ROADMAP.md](docs/ROADMAP.md) secties "🎯 Planningssessie", "✅ Uitvoering" en "✅ Vervolg (avond)" — alle drie 15 augustus 2026

---

## Waar we nu staan (in één alinea)

**De externe-IMU-rotatiebug is opgelost, geen workaround meer.** Root cause: twee samenwerkende factoren — dynamische interferentie door nabijheid van het voedingsbord/de XT30-connector (verholpen door fysieke verplaatsing van de sensor), en een nooit-gekalibreerde hard-iron-afwijking (verholpen door een nieuwe magnetometer-kalibratie, `mag_calibration.py`). De magnetometer-as-remap, aanvankelijk verdacht, bleek na verificatie tegen het officiële ICM-20948-datasheet correct. `MAG_GAIN` staat weer op de originele 0,01 (correctie AAN) — gevalideerd tot binnen 0,1-2,1% van STM32/RF2O in beide rotatierichtingen én tijdens een complexere gecombineerde manoeuvre (180°-draai + vooruit + partiële draai, alle drie sensoren binnen 3,4° van elkaar).

**Ook afgerond deze sessie:** `MAX_LINEAR_SPEED_MPS` in `phoenix_driver.py` bevestigd correct (geen update nodig ondanks twee gait-wijzigingen sinds de laatste meting); RF2O x/y blijkt consistent ~6-7% te onderschatten (mogelijk met vaste factor te corrigeren); STM32-Hz-bus-contentie gekwantificeerd (2Hz kost nog steeds +87,8% overhead).

---

## Direct te doen, in deze volgorde

1. **Fysieke montagepositie van de externe IMU niet meer wijzigen** zonder de rotatietest te herhalen — de huidige positie + kalibratie is gevalideerd, maar de kalibratiewaarden (`MAG_OFFSET`/`MAG_SCALE` in `imu_publisher.py`) zijn positie-specifiek. Een nieuwe verplaatsing vereist een nieuwe `mag_calibration.py`-run.
2. **`robot_bridge.py`'s `SPEED_TABLE`/`STEP_DISTANCE_M`** — nog steeds niet vernieuwd. Ander bewegingspad (STM32-firmware-gait via `muto_driver_fixed.py`, gebruikt door Dify/spraak/HTTP) dan wat vandaag gekalibreerd is (`phoenix_gait.py`/Nav2-pad). Alleen relevant als dat pad ook gebruikt wordt.
3. **RF2O x/y-correctiefactor overwegen (~1,068×)** — n=2 richtingen, sterk maar nog voorlopig signaal.
4. **Residual-gate-node en stop-and-correct-navigatielus nog niet gebouwd** — de karakteriseringsdata daarvoor is nu wel compleet (zie ROADMAP.md secties A/C van de planningssessie).
5. **STM32-Hz-bus-contentie blijft bestaan, ook bij 2Hz** (+87,8% wall-clock-overhead, plafond ~3,4Hz werkelijk haalbare rate) — geen actie ondernomen, alleen gekwantificeerd.
6. **180°-laser-TF-fix blijft elke sessie checken** (container-lokale `sed`-aanpassing, niet persistent).

---

## Openstaande bugs (nog niet gefixt)

- **Nav2 `NavigateToPose` liep veel verder dan het doel** (30cm werd >50cm, 17 recoveries, 14 aug) — vandaag niet aangeraakt.
- **`phoenix_driver.py` kan stil crashen** (14 aug) — vandaag niet aangeraakt.

---

## Bewust uitgesteld (lagere prioriteit, met reden)

- **Zijwaartse drift tijdens recht-vooruit-lopen** — ongewijzigd.
- **Pad B (zachte gait-variant)** — on hold, ongewijzigd.
- **Astra Pro Plus + ICP-pointcloud-odometrie** — blijft geparkeerd. Met zowel de externe-IMU-rotatie als RF2O x/y nu redelijk goed gekarakteriseerd (en beide bruikbaar, eventueel met een simpele correctiefactor voor RF2O), is de noodzaak voor een extra sensor verder afgenomen.

---

## Belangrijke, blijvende lessen uit deze sessie (15 augustus 2026)

- **Een fysiek probleem kan zich als een softwarebug voordoen, en andersom — verifieer beide kanten voordat je concludeert.** De as-remap leek de meest waarschijnlijke oorzaak (stond al als verdacht in de docstring), maar bleek na daadwerkelijke verificatie tegen het datasheet correct; de echte oorzaak was een combinatie van montage-plaatsing (hardware) en ontbrekende kalibratie (software/proces). Beide moesten worden aangepakt — geen van beide alleen was genoeg.
- **Bij twijfel over een fysieke oorzaak: vraag om foto's van de daadwerkelijke montage.** De aanname "IMU zit al in de geïsoleerde positie van 11 augustus" bleek onjuist zodra er foto's kwamen — de sensor zat vlak boven het voedingsbord. Een verbale bevestiging ("ja, verhoogde positie") was niet betrouwbaar genoeg voor deze diagnose.
- **Foutpatronen zijn diagnostisch: chaotisch/teken-wisselend wijst op dynamische storing, consistent/richtingsonafhankelijk op statische storing.** Dat onderscheid hielp bepalen welke van de twee fixes (verplaatsen vs. kalibreren) op welk moment het meest opleverde.
- **Reken een fysieke hypothese (zoals off-axis-centripetale versnelling) na met echte getallen voordat je hem serieus neemt of verwerpt.** Een plausibel klinkend mechanisme bleek bij dit tempo/deze montage-afstand drie ordes van grootte te klein om de waargenomen fout te verklaren — een korte berekening voorkwam een verkeerd spoor.
- **Een polling-loop die "wacht tot data klaar is" (zoals `read_magnetometer_data(timeout=1.0)`) kan een vast-aantal-stappen-lus enorm uitrekken in wall-clock-tijd, zonder dat het een vastloper is.** Zelfde patroon als de STM32-Hz-bevinding eerder vandaag — bij twijfel: `etimes` van het proces checken (stijgt het nog?) i.p.v. aannemen dat het vastzit.
- (Blijft gelden, uit eerdere sessies) Altijd de daadwerkelijk actieve config/hardware-status verifiëren voordat je op een eerdere sessie's aannames voortbouwt; code op de Pi-host kan afwijken van de container; minimaal ~24-27s wachten na een stop voor een betrouwbare yaw/pose-meting.
