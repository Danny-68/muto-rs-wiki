# 🔄 Overdracht — lees dit eerst in een nieuwe sessie

**Laatst bijgewerkt:** 15 augustus 2026 (nacht, sessie afgesloten)
**Volledige details:** [docs/ROADMAP.md](docs/ROADMAP.md), sectie "✅ Nav2-hertest 15 augustus 2026 (nacht)" bovenaan (nieuwste eerst)

---

## Waar we nu staan (in één alinea)

De externe-IMU-rotatiebug is opgelost (zie eerdere secties). Vanavond is een Nav2-hertest gedaan: de eerste `NavigateToPose`-poging liep mis (robot richting muur, geen schade) door `inflation_radius: 1.0` — veel te groot voor deze kleine kamer, waardoor de startpositie zelf als "lethal space" werd gezien en Nav2's blinde `backup`-recovery aansloeg. Gefixt (`inflation_radius` → 0,35). Bij het opnieuw verifiëren van de AMCL-lokalisatie zijn **twee onafhankelijke echte bugs** gevonden en gefixt: (1) de LiDAR-driver vulde onbeantwoorde hoeken met 0,0m i.p.v. ongeldig (C++ resize-default, 33,5% van de scan was vals), en (2) `verify_amcl_pose.py` miste zelf de 180°-correctie voor de gedraaide LiDAR-montage. Na beide fixes bleek de lokalisatie steeds prima te zijn geweest — de gebruiker had dat visueel al correct ingeschat, de metingsscript loog.

**Er is nog geen nieuwe `NavigateToPose`-poging gedaan** na al deze fixes — dat is de directe volgende stap.

---

## Direct te doen, in deze volgorde

1. **Nieuwe, voorzichtige `NavigateToPose`-poging** met de huidige fixes (inflation_radius, odom_topic→odom_fused, LiDAR-driver, verify-script) — dit is nooit getest na de fixes. Begin kort (~0,5m), zoals eerder.
2. **Cleanup-besluit nemen over de 3 ongebruikte LiDAR-driver-kopieën** (`yahboomcar_ros2_ws/src/`, `software/src/`, `software/library_ws/src/` — alleen `software/library_ws_humble/src/` wordt geladen). Nog open: documenteren als ongebruikt, of verwijderen?
3. **De originele 14-augustus-`NavigateToPose`-bug (30cm werd >50cm) nog niet 1-op-1 bevestigd opgelost** — de `inflation_radius`-fix is een sterke kandidaat-verklaring maar niet expliciet tegen die oude sessie getest.
4. **`robot_bridge.py`'s `SPEED_TABLE`/`STEP_DISTANCE_M`** — nog steeds niet vernieuwd (ander bewegingspad, zie eerdere sessie-secties).
5. **RF2O x/y-correctiefactor overwegen (~1,068×)** — n=2, nog voorlopig.
6. **Residual-gate-node en stop-and-correct-navigatielus nog niet gebouwd.**
7. **180°-laser-TF-fix blijft elke sessie checken** — dit keer bevestigd nog actief (`frame_id: laser_scan_fix` correct geladen), maar niet persistent, dus opnieuw checken bij een volgende container-restart.

---

## Openstaande bugs (nog niet gefixt)

- **`phoenix_driver.py` kan stil crashen** (14 aug) — vandaag niet aangeraakt.
- **3 ongebruikte LiDAR-driver-kopieën** — zie "Direct te doen" punt 2, geen bug maar wel een opruimpunt.

---

## Bewust uitgesteld (lagere prioriteit, met reden)

- **Zijwaartse drift tijdens recht-vooruit-lopen** — ongewijzigd.
- **Pad B (zachte gait-variant)** — on hold, ongewijzigd.
- **Astra Pro Plus + ICP-pointcloud-odometrie** — blijft geparkeerd, nog minder reden dan eerder (zie reflectiesectie).

---

## Belangrijke, blijvende lessen uit deze sessie (15 augustus 2026, Nav2-deel)

- **Een blinde `backup`-recovery-beweging (geen geldig, obstakel-gecontroleerd pad) kan een robot richting een muur sturen zonder dat de "eigenlijke" navigatie iets fout doet.** Als een Nav2-poging onverwacht gevaarlijk beweegt, check eerst of de planner ooit een geldig pad kreeg (`Starting point in lethal space`-achtige meldingen) vóórdat je een dieper besturingsprobleem vermoedt.
- **`inflation_radius` moet in verhouding staan tot de kamergrootte, niet alleen tot de robotgrootte.** 4× de robot-radius was veel te groot voor deze kleine ruimte — een waarde die in een groot magazijn prima zou zijn, blokkeerde hier bijna alle vloeroppervlak.
- **Een grote, numerieke afwijking in een verificatiescript is niet per definitie een echt probleem — controleer het verificatiescript zelf net zo kritisch als wat het verifieert.** Twee keer vanavond bleek de "meting" fout te zijn, niet de werkelijkheid (LiDAR-driver leek eerst het probleem, uiteindelijk was het `verify_amcl_pose.py` zelf). Vertrouw een mens die zegt "dat klopt niet met wat ik zie" — dat leidde beide keren naar de echte bug.
- **Een consistente, brede (~40°+) 0,0m-sector in scandata is typisch een software-zerofill-artefact, geen sensorfout** — vraag altijd eerst om fysieke bevestigging (is er iets in de weg?) voordat je een hardwarehypothese volgt; hier bleek het een C++-`resize()`-default.
- **Bij het patchen van een gedeelde/gevendorde driver: check eerst of er meerdere kopieën van de broncode bestaan** voordat je aanneemt dat één fix overal doorwerkt. Hier bleken vier bijna-identieke workspace-kopieën te bestaan, waarvan er maar één daadwerkelijk geladen wordt.
- (Blijft gelden) Code op de Pi-host/in een repo kan afwijken van wat er in de container daadwerkelijk draait — altijd verifiëren welk exact pad geladen wordt (`$L`/`$N` in de opstartscripts) vóórdat je een fix aanbrengt.
