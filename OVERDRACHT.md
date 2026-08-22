# 🔄 Overdracht — lees dit eerst in een nieuwe sessie

**Laatst bijgewerkt:** 21 augustus 2026 (avond)
**Volledige details:** [docs/ROADMAP.md](docs/ROADMAP.md), secties "🧭 Vervolg 21 augustus 2026" en "⚠️ Vervolg 16 augustus 2026" bovenaan (nieuwste eerst)

---

## Waar we nu staan (in één alinea)

Na maanden herhaalde AMCL-mislukkingen is het kernprobleem erkend als
**fundamenteel, niet tunebaar**: pure LiDAR scan-matching kan een
symmetrische gang structureel niet oplossen. Besloten: stoppen met
AMCL-parameters bijstellen, in plaats daarvan **AprilTag + Astra-camera**
toevoegen als absoluut lokalisatie-anker (volledige analyse + 8-fasen
stappenplan: [Muto Lokalisatie Routekaart](https://claude.ai/code/artifact/10f95581-291a-4066-ad52-023ef76f3f2a)).
Onderweg is een **tweede, los probleem** gevonden en verholpen: `base_link`'s
eigen URDF +x-as wijst structureel naar de fysieke achterkant van de robot
(vast, 180°, niets met AMCL/de gang te maken) — nu gecentraliseerd in
`/home/pi/muto_front_convention.py`, met alle weergavescripts daarop
aangesloten. Ook vastgesteld: AMCL convergeert **nooit** stilstaand vanuit
een volledige reset (dat is normaal MCL-gedrag, geen bug) — er blijft dus
een bewegingsgebaseerde disambiguatieprocedure nodig voor echte
kaartlokalisatie.

---

## Direct te doen, in deze volgorde

1. **`lidar_overlay.py` en `verify_amcl_pose.py` los live verifiëren** zodra
   AMCL daadwerkelijk convergeert — ze gebruiken nu hetzelfde patroon als
   het live-bevestigde `front_scan_check.py`, maar zijn zelf nog niet apart
   getest. Vereist beweging (rotatie-disambiguatie) + expliciete toestemming
   vlak vooraf.
2. **Nieuwe kaart opnemen** — staand besluit sinds 16 augustus, nooit
   uitgevoerd, nu logisch te combineren met een AprilTag zichtbaar tijdens
   de opname (Fase 6 van de routekaart).
3. **AprilTag Fase 1 starten** (software voorbereiden): `ros-humble-apriltag-ros`
   installeren in `humble_run` (alleen `apriltag-msgs` staat al), tag kiezen
   en printen, camera lichtgewicht opstarten (puur tag-detectie, geen
   RTAB-Map). Zie de routekaart voor alle 8 fases.
4. **STM32-onboard-yaw niet vertrouwen buiten korte, geïsoleerde
   testbewegingen** — nog steeds geldig, ongewijzigd sinds 15 aug. Externe
   IMU (via `/odom_fused`) blijft de betrouwbaardere bron voor echte
   navigatie.
5. **Waarom de Muto op 15 aug vastliep is nooit onderzocht** — nog steeds
   openstaand, geen nieuwe informatie sindsdien.

---

## Openstaande bugs (nog niet gefixt)

- **AMCL-convergentie op `lidar_only_map.yaml` blijft situationeel
  onbetrouwbaar in de gang** — dit is nu het hoofdpunt achter het
  AprilTag-besluit, geen losse bug meer om te "fixen" via tuning.
- **Muto liep op 15 aug vast, oorzaak nog onbekend.**
- **`phoenix_driver.py` kan stil crashen** (14 aug) — nog steeds niet
  onderzocht.
- **`lidar_overlay.py`/`verify_amcl_pose.py` nog niet los live
  geverifieerd** na de front-conventie-fix (zie hierboven).

---

## Bewust uitgesteld (lagere prioriteit, met reden)

- **Zijwaartse drift tijdens recht-vooruit-lopen** — ongewijzigd.
- **Pad B (zachte gait-variant)** — on hold, ongewijzigd.
- **Astra Pro Plus + ICP-pointcloud-odometrie** — geparkeerd; de camera
  wordt nu wel weer gebruikt, maar puur voor AprilTag-detectie, niet voor
  ICP/SLAM.

---

## Belangrijke, blijvende lessen uit 21 augustus 2026

- **AMCL-symmetrie-ambiguïteit en de base_link-voorkant-conventiefout zijn
  twee aparte, allebei-echte problemen** — niet aannemen dat het ene het
  andere verklaart. Test ze los: `front_scan_check.py` (kaart/AMCL-vrij) voor
  de conventie, de volledige rotatie+verplaatsing-procedure voor echte
  kaartlokalisatie.
- **Eén correctie-constante hoort op precies één plek te leven.** De oude
  `FRONT_DISPLAY_OFFSET_DEG`-hack stond alleen in `lidar_overlay.py` en ging
  stilzwijgend verloren toen dat script om een andere reden werd aangepast.
  Nu in `/home/pi/muto_front_convention.py`, geïmporteerd door elk script
  dat de fysieke voorkant moet tonen — wijzig het daar, nooit een kopie
  elders hardcoden.
- **AMCL convergeert niet stilstaand vanuit een volledige reset, hoe lang je
  ook wacht** — `update_min_d`/`update_min_a` poorten de update-stap op
  beweging, niet op tijd. Dit is standaard MCL-gedrag, geen projectbug; ga
  er niet meer vanuit dat "even wachten" genoeg is.
- **Bij het consolideren van een fix altijd de buurcode meenemen.**
  `verify_amcl_pose.py` had exact hetzelfde risico als de losse
  front-conventie-hack (één regel gecorrigeerd, de regel ernaast niet) —
  alleen gevonden omdat er expliciet gezocht werd naar andere plekken met
  dezelfde soort inconsistentie.
- (Blijft gelden, sinds 15 aug) **Altijd expliciet vragen om
  ruimte-bevestiging vlak vóór élke aparte beweging** — een eerdere
  algemene instemming geldt niet automatisch voor een volgende actie. De
  gebruiker bepaalt altijd zelf het navigatiedoel. Na elke test eerst de
  positie-tekening tonen.
- (Blijft gelden, sinds 15 aug) `pkill -f <procesnaam>` i.p.v. een exact PID
  laat bovenliggende `ros2 launch`-wrappers en losse
  `static_transform_publisher`-processen als wees achter.
- (Blijft gelden) Code op de Pi-host/in een repo kan afwijken van wat er in
  de container draait; bestandswijzigingen overleven een reboot,
  proces-state niet.
