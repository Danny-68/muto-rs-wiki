# 🔄 Overdracht — lees dit eerst in een nieuwe sessie

**Laatst bijgewerkt:** 14 augustus 2026, middag
**Volledige details:** [problems/PROBLEMS.md](problems/PROBLEMS.md) sectie "🧭 AMCL-lokalisatie: bewezen procedure + 180°-voor/achter-weergavebug (14 augustus 2026)", [docs/ROADMAP.md](docs/ROADMAP.md)

---

## Waar we nu staan (in één alinea)

Grote stap vooruit t.o.v. 11 augustus: er is nu een **bewezen, herhaalbare AMCL-lokalisatieprocedure** — een brute-force grid-search over (x, y, yaw) samen die scoort hoeveel scanpunten op een muur vallen (`xy_yaw_grid_match.py`/`wide_grid_match.py`), gevolgd door een visuele scan-overlay-bevestiging door de gebruiker (`lidar_overlay.py`). Onderweg zijn twee losse, belangrijke bugs gevonden en gefixt: (1) `incremental_rotate.py`'s settle-wachttijd gebruikte een `spin_once`-lus i.p.v. `time.sleep()` en wachtte dus geen echte 27s — gefixt; (2) de diagnostische scripts toonden de "voorkant"-pijl consequent 180° verkeerd om (twee keer onafhankelijk bevestigd, kamer én gang) — dit bleek een weergavebug in de eigen Python-tooling, **niet** in AMCL/Nav2's eigen TF-keten; gefixt met een apart display-only offset zodat de aan AMCL doorgegeven yaw (de scan-matching-correcte waarde) niet meer aangeraakt wordt.

Linksom-rotatiesnelheid is gekalibreerd: **~0,081 rad/s** (via de onboard STM32-IMU — de externe IMU gaf bij linksom-metingen inconsistente/zelfs verkeerd-om resultaten, terwijl de identieke test tegen de STM32-IMU wél consistent was, over 5 segmenten).

**Belangrijke architectuurwijziging vanavond:** de gebruiker heeft de **externe ICM20948-IMU losgekoppeld** (voor de zekerheid, na een mislukte eerste Nav2-test). `imu_publisher.py` faalt nu structureel ("Timeout waiting for Magnetometer Ready") en is gestopt. EKF draait nu op een aangepaste config (`ekf_params_stm32_yaw.yaml`) die yaw uit de **onboard STM32-IMU** (`/imu_stm32`) haalt i.p.v. Pad A's externe IMU. Dit is dus terug naar de situatie van vóór Pad A (11 aug) — Pad A's externe-IMU-aanpak staat on hold zolang de sensor niet weer aangesloten is.

Eén Nav2 `NavigateToPose`-test (30cm vooruit, bij de deuropening) **mislukte**: 17 recovery-pogingen in 58s, robot liep veel verder (>50cm, niet in rechte lijn) dan bedoeld — root cause nog niet onderzocht. Gebruiker heeft de robot daarna handmatig naar de gang verplaatst (meer ruimte) voor een herhaalde, voorzichtiger geobserveerde poging.

**Robot staat momenteel stil in de gang**, lokalisatie daar bevestigd (grid-search 83% match + visuele bevestiging, positie x=-0,60 y=-3,80 in map-frame, voorkant-weergave gecorrigeerd). Software-stack draait (lidar/rf2o/EKF-met-STM32-yaw/phoenix_driver/Nav2), driver herstart met `python3 -u` voor directe logging (zie hieronder waarom).

---

## Direct te doen, in deze volgorde

1. **Onderzoek waarom de eerste Nav2 `NavigateToPose`-test (30cm, deuropening) 17 recoveries gaf en de robot veel verder liet lopen dan bedoeld.** Nog niet gediagnosticeerd — mogelijk costmap-probleem (zie eerdere `inflation_radius`-issue), mogelijk controller-tuning, mogelijk een lokalisatie-sprong tijdens het navigeren zelf. Check `/tmp/nav2.log` en de costmap-configuratie voordat je een volgende `NavigateToPose`-poging doet.
2. **Externe IMU weer aansluiten (of definitief beslissen 'm te laten voor wat die is)** — zolang die loskoppeld blijft, draait alles op de STM32-onboard-yaw-config (`ekf_params_stm32_yaw.yaml`), niet Pad A. Als de externe IMU terugkomt: EKF weer terugzetten naar `ekf_params.yaml` (Pad A) én opnieuw goed testen of het linksom-inconsistentieprobleem (zie PROBLEMS.md) dan nog optreedt.
3. **Vervolg Nav2-obstakeltest in de gang** (meer ruimte dan bij de deuropening) — met engere bewaking dan de vorige poging: controleer tussentijds `number_of_recoveries` en `distance_remaining`, en wees bereid vroeg te annuleren.
4. **180°-laser-TF-fix blijft elke sessie checken** (container-lokale `sed`-aanpassing, niet persistent) — zie eerdere instructies, ongewijzigd.
5. **`verify_amcl_pose.py` niet meer gebruiken** zonder eerst de hoek-conventie te fixen — zie PROBLEMS.md, geeft misleidende resultaten (zowel valse "klopt niet" als valse "klopt wel").

---

## Openstaande bugs (nog niet gefixt)

- **Nav2 `NavigateToPose` liep veel verder dan het doel (30cm werd >50cm, 17 recoveries)** — root cause onbekend, zie punt 1 hierboven.
- **Externe IMU geeft inconsistente/foutieve metingen specifiek bij linksom-rotatie** (4x snelheidsvariatie + één segment met omgekeerde richting), terwijl dezelfde test tegen de STM32-onboard-IMU wél consistent was. Nog niet onderzocht of dit een magnetometer-interferentie-probleem is dat specifiek bij linksom-beweging optreedt, of een resterend montageprobleem. Momenteel omzeild door de externe IMU los te koppelen en STM32-yaw te gebruiken — geen structurele fix.
- **`phoenix_driver.py` kan stil crashen** (geen traceback, geen OOM, geen USB-disconnect zichtbaar in logs) — reden onbekend. Altijd `ps -eo pid,cmd | grep phoenix_driver.py` checken vóór/na elk bewegingscommando. Start voortaan met `python3 -u` (ongebufferd) zodat een crash direct zichtbaar is in de log i.p.v. pas bij het volgende flush-moment.

---

## Bewust uitgesteld (lagere prioriteit, met reden)

- **Zijwaartse drift tijdens recht-vooruit-lopen** — ongewijzigd t.o.v. 11 augustus, nog niet herzien.
- **Pad B (zachte gait-variant)** — on hold, ongewijzigd.
- **Astra Pro Plus + ICP-pointcloud-odometrie** — on hold als stap-2-fallback, ongewijzigd. Zie ook de nieuwe externe-IMU-linksom-onbetrouwbaarheid hierboven als extra argument om dit soms te herzien als de externe IMU problematisch blijft.

---

## Belangrijke, blijvende lessen uit deze sessie (14 augustus 2026)

- **Rotatie-only lokalisatie is onvoldoende, zelfs met een volledige 2-cirkel-spin** — gebruik een gecombineerde (x,y,yaw) grid-search-scanmatch i.p.v. AMCL's eigen particle filter blind te vertrouwen op deze kaart. Zie PROBLEMS.md voor de volledige procedure.
- **180°-voor/achter-ambiguïteit in scan-matching komt vaker voor dan gedacht** — niet alleen lange gangen, ook een relatief kleine, min-of-meer symmetrische kamer gaf een scan-match die 180° verkeerd om was. Los dit NOOIT op door de aan AMCL doorgegeven pose te flippen — corrigeer alleen de weergave (zie `FRONT_DISPLAY_OFFSET_DEG` in `lidar_overlay.py`).
- **Plaatjes/schetsen laten interpreteren voor precieze hoeken is foutgevoelig** — meerdere keren deze sessie verkeerd afgelezen (zowel door de assistent als in de communicatie erover). Objectieve scan-matching (grid-search) is betrouwbaarder dan visuele educated guesses, maar zelfs dan is een laatste menselijke bevestiging nodig bij 180°-symmetrie.
- **Eén sensor onafhankelijk cross-checken tegen een andere kan een sensorprobleem isoleren** — de linksom-kalibratie-inconsistentie bleek specifiek aan de externe IMU te liggen, niet aan de robot/gait, doordat dezelfde test tegen de STM32-onboard-IMU wél consistent was.
- (Blijft gelden, uit eerdere sessies) **Nooit een lange, blinde rotatieduur commanderen** op basis van een niet-gevalideerde snelheid; **wachttijden altijd met `time.sleep()`**; **minimaal ~24-27 seconden wachten na elke stop** voor een betrouwbare yaw/pose-meting.
