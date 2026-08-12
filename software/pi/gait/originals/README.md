# Beschermde originelen

`phoenix_gait_ORIGINAL_VALIDATED_10aug2026.py` — de op 10 augustus 2026
"standalone gevalideerde" versie van `phoenix_gait.py` (continu fasemodel,
sinusoïdale easing, tripod/ripple/wave/centipede, body_sway + body_dip,
snelheidsafhankelijke lift, HW-servo-interpolatie). Dit was de precieze,
weinig-drift-vertonende versie waarop `phoenix_driver.py` is gebouwd.

**Regel: dit bestand nooit overschrijven.** Op 11 augustus 2026 (avond) is,
na een onverklaarde zijwaartse drift tijdens een rechte-lijn-test, expliciet
geverifieerd (byte-voor-byte diff) dat de live `phoenix_gait.py` nog exact
gelijk is aan dit bestand — geen regressie. Gebruik deze kopie als
referentiepunt bij toekomstige twijfel of `phoenix_gait.py` nog intact is:

```bash
diff software/pi/gait/originals/phoenix_gait_ORIGINAL_VALIDATED_10aug2026.py /home/pi/phoenix_gait.py
```
