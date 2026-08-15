# 🔄 Overdracht — lees dit eerst in een nieuwe sessie

**Laatst bijgewerkt:** 15 augustus 2026 (diep in de nacht, sessie afgesloten na een vastgelopen Muto + reboot)
**Volledige details:** [docs/ROADMAP.md](docs/ROADMAP.md), sectie "⚠️ Vervolg 15 augustus 2026 (diep in de nacht)" bovenaan (nieuwste eerst)

---

## Waar we nu staan (in één alinea)

Een lange sessie met veel vooruitgang én een onopgelost probleem aan het eind. **Positief:** de externe-IMU-rotatiebug is definitief opgelost (kalibratie + herpositionering), `inflation_radius` en `odom_topic` zijn gefixt, twee echte LiDAR/verificatie-bugs zijn gevonden en gefixt, en de **eerste geslaagde `NavigateToPose` van het hele project** is gelukt. **Negatief:** ná die geslaagde test bleek AMCL herhaaldelijk verkeerd te convergeren (twee van drie verse pogingen faalden met ~56-61° fout), en STM32-onboard-yaw bleek onbetrouwbaar te worden na een langere/Nav2-aangestuurde beweging (geen magnetometer-correctie, in tegenstelling tot de externe IMU). Twee echte weesprocessen zijn gevonden en opgeruimd (een oude LiDAR-launch-wrapper en een dubbele `static_transform_publisher`, beide ~90-100 minuten oud), maar verklaren niet de volledige AMCL-instabiliteit. **De sessie eindigde doordat de Muto zelf vastliep en de gebruiker een fysieke reboot moest doen** — oorzaak nog niet onderzocht.

---

## Direct te doen, in deze volgorde

1. **Volledige stack fris opstarten** — container is leeg na de reboot, niets draait. Alle bestandsfixes van vanavond staan nog: LiDAR-driverpatch (`ranges.resize(size, NaN)`), `odom_topic: odom_fused` (bt_navigator + controller_server), `inflation_radius: 0.35`, magnetometer-kalibratie in `imu_publisher.py` (`MAG_OFFSET`/`MAG_SCALE`, `MAG_GAIN=0.01`).
2. **Bij het herstarten van welk onderdeel dan ook: gebruik exacte PID's om te stoppen, nooit `pkill -f <naam>`** — dat laat bovenliggende `ros2 launch`-wrappers en/of losse `static_transform_publisher`-processen als wees achter. Dit gebeurde twee keer vanavond (90 min en 103 min ongemerkt actief) en was een reële bijdragende factor aan de AMCL-problemen.
3. **AMCL blijft onbetrouwbaar op deze kaart — dit is het belangrijkste openstaande probleem.** Voordat je nog een keer dezelfde rotatie+verplaatsing-relokalisatieprocedure probeert: overweeg eerst de AMCL-parameters in `hexapod_nav_params.yaml` te bekijken (deeltjesaantal, `update_min_a`/`update_min_d`, laser-bereik) en overweeg of de kaart zelf (`lidar_only_map.yaml`, zichtbaar rommelig/met straal-artefacten) opnieuw opgenomen moet worden.
4. **STM32-onboard-yaw niet meer vertrouwen als referentie buiten korte, geïsoleerde testbewegingen** (zoals vandaag's `combi_calibration_test.py`-stijl tests). Voor alles wat met Nav2/echte navigatie te maken heeft: de externe IMU (via `/odom_fused`) is de betrouwbaardere bron.
5. **180°-hypothese van de gebruiker nog niet echt getest** — vereist een wijziging in de URDF's `laser_scan_fix_joint` (niet de `ydlidar_launch.py`-`static_transform_publisher`, die bleek een dode tak in de TF-boom te zijn, los van wat AMCL/rf2o daadwerkelijk gebruiken).
6. **Uitzoeken waarom de Muto aan het einde van de sessie vastliep** — geen diagnose gedaan, de sessie eindigde direct na de reboot-melding.
7. **Drie nieuwe, blijvende procesregels** (zie hieronder "Belangrijke lessen") — vooral: altijd expliciet om ruimte/toestemming vragen vóór elke aparte beweging, gebruiker bepaalt altijd zelf het navigatiedoel, na elke test eerst de positie-tekening tonen.

---

## Openstaande bugs (nog niet gefixt)

- **AMCL-convergentie op `lidar_only_map.yaml` is niet betrouwbaar herhaalbaar** — nieuw, belangrijk, hoofdprobleem van vanavond. Zie ROADMAP.md voor de volledige onderzoeksgeschiedenis.
- **Muto liep vast, oorzaak onbekend** — nieuw, nog geen onderzoek gedaan.
- **`phoenix_driver.py` kan stil crashen** (14 aug) — nog steeds niet onderzocht.

---

## Bewust uitgesteld (lagere prioriteit, met reden)

- **Zijwaartse drift tijdens recht-vooruit-lopen** — ongewijzigd.
- **Pad B (zachte gait-variant)** — on hold, ongewijzigd.
- **Astra Pro Plus + ICP-pointcloud-odometrie** — blijft geparkeerd.
- **URDF-gebaseerde 180°-test** — bewust niet vanavond gedaan, te riskant na alles wat al misging; apart, geïsoleerd oppakken.

---

## Belangrijke, blijvende lessen uit deze sessie (15 augustus 2026)

- **Nieuw staand beleid, expliciet gevraagd door de gebruiker:**
  1. Altijd expliciet vragen om ruimte-bevestiging vlak vóór élke aparte beweging — een eerdere algemene instemming geldt niet automatisch voor een volgende actie.
  2. De gebruiker bepaalt altijd zelf het navigatiedoel/de locatie, nooit zelf een doel kiezen.
  3. Na elke test eerst de positie-tekening (kaart + LiDAR-overlay) tonen, vóór een volgende stap.
- **`pkill -f <procesnaam>` i.p.v. een exact PID laat bovenliggende `ros2 launch`-wrappers en aparte `static_transform_publisher`-processen als wees achter.** Twee keer vanavond ongemerkt 90-100 minuten actief gebleven, met een reële kans dat dit bijdroeg aan AMCL-instabiliteit (TF-dubbelzinnigheid). Gebruik voortaan exacte PID's bij het stoppen van een launch-boom.
- **Bij twijfel over een "gekke meting": controleer eerst de hele proceslijst op duplicaten/wezen, niet alleen de meting zelf.** Dat leverde deze sessie twee echte vondsten op die puur cijfermatig onderzoek had gemist.
- **STM32-onboard-yaw is alleen bewezen betrouwbaar bij korte, geïsoleerde testbewegingen (geen magnetometer-correctie, dus geen herstel van opgebouwde drift).** Bij langere of Nav2-aangestuurde bewegingen: niet meer als referentie gebruiken, de externe IMU/EKF is dan betrouwbaarder.
- **Niet elke plausibele hypothese hoort bij dezelfde transformatie thuis.** De 180°-test raakte een dode tak in de TF-boom (`laser_frame`, ongebruikt) i.p.v. de daadwerkelijk relevante URDF-relatie (`laser_scan_fix`) — eerst de TF-boom-structuur zelf controleren (welke frames zijn daadwerkelijk met elkaar verbonden) voordat je een transformatie aanpast.
- **Een cascade van kleine "fixes" bovenop een mogelijk al foute staat verergert het probleem eerder dan dat het helpt.** Bij een onzekere staat: eerst een schone, volledige herstart overwegen in plaats van gedeeltelijke correcties te stapelen.
- **Oude coördinaten teruggeven werkt niet als de robot fysiek is verplaatst sinds die coördinaten golden** — dat is geen "instellingen herstellen", dat is een positie opleggen die niet meer bij de werkelijkheid past.
- (Blijft gelden) Code op de Pi-host/in een repo kan afwijken van wat er in de container draait; bestandswijzigingen overleven een reboot, proces-state niet.
