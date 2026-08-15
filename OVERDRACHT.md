# 🔄 Overdracht — lees dit eerst in een nieuwe sessie

**Laatst bijgewerkt:** 15 augustus 2026
**Volledige details:** [docs/ROADMAP.md](docs/ROADMAP.md) sectie "🎯 Planningssessie 15 augustus 2026"

---

## Waar we nu staan (in één alinea)

**Dit was een pure planningssessie — geen hardware aangeraakt, geen bewegingscommando's gegeven, geen code gewijzigd.** We hebben de odometrie-/lokalisatiearchitectuur doorgesproken (RF2O-yaw-uitfasering, IMU-taakverdeling, een "stop-and-correct"-navigatiestrategie met LiDAR/AMCL, en een gevonden gat in de afstandskalibratie) en dat uitgewerkt tot een concreet vervolgplan. Volledige onderbouwing en het stappenplan staan in ROADMAP.md.

**⚠️ Belangrijkste openstaande vraag, eerst checken:** deze sessie is gevoerd uitgaand van `ekf_params.yaml` (Pad A, externe ICM20948 als primaire yaw) als de actuele configuratie. Maar de **vorige** overdracht (14 aug) meldt dat de externe IMU die avond is **losgekoppeld** (`imu_publisher.py` faalde structureel — "Timeout waiting for Magnetometer Ready") en dat de EKF sindsdien draait op `ekf_params_stm32_yaw.yaml` (STM32-onboard-yaw). **Niet geverifieerd of dit inmiddels weer is opgelost.** Een deel van het vandaag besproken plan (IMU-karakterisering van de ICM20948) is pas uitvoerbaar als de externe IMU weer fysiek aangesloten en functioneel is — zie punt 1 hieronder.

---

## Direct te doen, in deze volgorde

1. **Controleer eerst de fysieke/software-status van de externe ICM20948** — zit hij aangesloten, en geeft `imu_publisher.py` nog steeds de magnetometer-timeout-fout? Zo ja: eerst dat oplossen (of bewust beslissen voorlopig op STM32-yaw te blijven draaien) vóórdat je verdergaat met punt 2. Zo nee (weer aangesloten en werkend): terugzetten naar `ekf_params.yaml` (Pad A) en pas dan verder.
2. **Eén combi-testscript bouwen en draaien** dat tegelijk afdekt: IMU-karakterisering (bias/drift/gait-gedrag van de externe IMU, ev. ook STM32-yaw ter vergelijking), RF2O x/y-betrouwbaarheid tijdens gait, yaw-rate-residual IMU-vs-RF2O, én een verse afstandskalibratie (huidige `SPEED_TABLE`/`STEP_DISTANCE_M` zijn aantoonbaar verouderd, zie ROADMAP.md). Bouwt voort op `phoenix_yaw_drift_test.py` (yaw-logpatroon) + `logs/forward_drift_test*.py` (afstandsmeting), aangevuld met een in-place-draai-variant (geen netto translatie) om vibratie-invloed te scheiden van translatie+rotatie.
3. **`robot_bridge.py`'s `SPEED_TABLE`/`STEP_DISTANCE_M` bijwerken** met de nieuwe metingen (met dateringscomment, zoals nu al gebruikelijk).
4. **Veilige segmentlengte bepalen** voor een "stop-and-correct"-navigatielus, op basis van de driftcijfers uit punt 2.
5. **`guarded_navigate_test.py` uitbreiden tot een herhalende lus** (nu single-shot: settle → AMCL-poll → één doel) die de totale afstand in segmenten opknipt met een AMCL-correctie tussen elk segment. Hergebruik het bestaande `/pose_settling`-topic en de one-shot-AMCL-poll-workaround (`/amcl_pose` is latched, zie eerdere sessies). **Open vraag hierbij:** is een korte stop + één AMCL-poll betrouwbaar genoeg, of is de zwaardere, al bewezen (x,y,yaw)-grid-search-procedure uit de 14-augustus-sessie nodig? Eerst empirisch checken (AMCL-pose+covariance loggen bij korte stops, vergelijken met de grid-search-referentie) voordat je hierop vertrouwt.
6. **180°-laser-TF-fix blijft elke sessie checken** (container-lokale `sed`-aanpassing, niet persistent) — ongewijzigd advies uit eerdere sessies.

---

## Openstaande bugs (nog niet gefixt — overgenomen uit 14 augustus, vandaag niet aangeraakt)

- **Nav2 `NavigateToPose` liep veel verder dan het doel** (30cm werd >50cm, 17 recoveries) — root cause onbekend, nog te onderzoeken via `/tmp/nav2.log` en de costmap-configuratie.
- **Externe IMU gaf inconsistente/foutieve metingen specifiek bij linksom-rotatie** (4× snelheidsvariatie + één omgekeerd segment) — nog niet onderzocht of dit magnetometer-interferentie is die specifiek bij linksom optreedt, of een montageprobleem. Hangt samen met punt 1 hierboven.
- **`phoenix_driver.py` kan stil crashen** (geen traceback/OOM/USB-disconnect zichtbaar) — reden onbekend. Draait sinds 14 aug met `python3 -u` voor directe logging; blijf `ps -eo pid,cmd | grep phoenix_driver.py` checken rond bewegingscommando's.

---

## Bewust uitgesteld (lagere prioriteit, met reden)

- **Zijwaartse drift tijdens recht-vooruit-lopen** — ongewijzigd, nog niet herzien.
- **Pad B (zachte gait-variant)** — on hold, ongewijzigd.
- **Astra Pro Plus + ICP-pointcloud-odometrie** — vandaag opnieuw overwogen (als "RF2O-watchdog"/onafhankelijke tweede meting) en **bewust wéér geparkeerd**: geen bewijs dat RF2O x/y structureel faalt (dat is nog niet eens getest), en de Astra heeft vermoedelijk dezelfde kwetsbaarheid voor gait-vibratie/poot-occlusie als RF2O — zou dus geen bewezen onafhankelijke bron zijn. Alleen heroverwegen als na de RF2O-x/y-karakterisering (punt 2 hierboven) blijkt dat translatie structureel onvoldoende is.

---

## Belangrijke, blijvende lessen uit deze sessie (15 augustus 2026)

- **Altijd de daadwerkelijk actieve config/hardware-status verifiëren voordat je op een eerdere sessie's architectuur voortbouwt.** Deze hele sessie ging uit van Pad A (externe IMU) als actuele staat op basis van `ekf_params.yaml`, terwijl de laatste overdracht (14 aug) al meldde dat dit was teruggedraaid naar STM32-yaw. Bestandsdatums/comments checken (zoals hier uiteindelijk wel gedaan voor de gait-kalibratie) had dit eerder aan het licht gebracht.
- **Een snelheids-/afstandskalibratie is stilzwijgend ongeldig zodra de gait-mechaniek verandert.** `SPEED_TABLE` (1 juli) en de `forward/backward_drift_test`-logs (9 aug) bleken beide ouder dan twee daaropvolgende gait-wijzigingen (`fix_foot_delta.py` 10 aug, `deepen_splay.py` 12 aug) die de effectieve staplengte plausibel beïnvloeden. Vuistregel: na elke wijziging aan `phoenix_gait.py`'s bewegingsformules of de neutrale beenstand, snelheids-/afstandskalibratie als verdacht behandelen totdat opnieuw gemeten.
- **Yahboom's officiële GitHub-repo (`YahboomTechnology/Muto-RS`) bevat geen bruikbare referentiecode voor onze gait** — alleen cursus-PDF's, geen scripts. `phoenix_gait.py` is volledig eigen code; kalibratie moet altijd zelf gemeten worden, er is geen extern getal om tegenaan te leggen.
