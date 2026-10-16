

## CR57 – APRS-Lense: Zeilen neu geordnet, Pfad als Kette (✅ 16.10.2026)

### Erfassung (OE3GAS, 16.10.2026)

1. Monitorzeile umbauen: nach `<UI>` neue Zeile, dort ohne „aprs:“ gleich die Payload; neue Zeile,
   dann die Interpretation. „heard from“ entfällt in der Zeile (steht in der Detailansicht).
2. Den Pfad in der Lense grafisch darstellen: Chips mit kleinen Richtungspfeilen, z. B.
   OM0ODX → OE6XTR → OE3XWJ-10, sonst kein Text beim Pfad.

### Umsetzung

1. APRS-Zeilen (Knopf an): Kopf bis `<UI>`, darunter die farbige Payload, darunter der Klartext.
   Marke `aprs` und Chip „heard from …“ sind weg. Ohne Knopf bleibt die Zeile wie bisher.
   TinyBox-Web-GUI und Client gleich.
2. Lense, Zeile **Path**: nur noch die Kette Absender → Digipeater, die weitergegeben haben (mit
   Rufzeichen im Pfad). Die gehörte Station ist hervorgehoben; Hover verbindet sie mit der Zeile
   **Heard**. Ohne Digipeater steht nur der Absender da; hat ein Digi kein Rufzeichen
   eingetragen, endet die Kette mit „?“. Die Texte zu Aliasen und Resthops entfallen.
- Decoder liefert dafür `chain`. Tests in `tests/test_aprs.py`. Client-Version 2026.10.16.4.
