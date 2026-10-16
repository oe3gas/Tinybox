

## CR56 – APRS-Lense: Feinschliff und Fragen aus dem Betrieb (✅ 16.10.2026)

### Erfassung (OE3GAS, 16.10.2026)

1. Die APRS-Lense-Leiste erst einblenden, wenn der Knopf gedrückt ist. Knopf umbenennen auf
   „APRS Lense“.
2. Zwischen den einzelnen APRS-Aussendungen eine Trennlinie.
3. Frage zu einer Telemetrie-Definition von OE3CRA-2 über OE3XWJ-10: Welche Station habe ich
   hier tatsächlich gehört?
4. Frage zu OE3MZC-2: Was bedeutet „hF gateway“?
5. Diese Fragen soll auch die APRS-Lense beantworten.

### Umsetzung

1. Knopf **APRS Lense** (TinyBox und Client); aus, bis er gedrückt wird. Erst dann erscheinen
   Klartextzeilen und die Leiste. Der Zustand wird je Browser gemerkt (neuer Schlüssel, startet
   also bei allen einmal „aus“).
2. Jede APRS-Aussendung hat oben und unten eine feine Linie.
3. Neue Zeile **Heard** im Adressteil der Lense, dazu der Chip „heard from …“ in der
   Klartextzeile: gehört hat man den **letzten Digipeater, der das Paket weitergegeben hat** (er
   steht mit `*` als letzter Rufzeichen-Eintrag vor den verbrauchten Aliasen), ohne `*` im Pfad
   den Absender selbst. Hat der letzte Digipeater sein Rufzeichen nicht eingetragen, sagt die
   Lense, dass es nicht erkennbar ist. Hover zeigt den passenden Pfad-Eintrag.
4. „hF gateway“ war ein Fehler beim Kleinschreiben – jetzt „HF gateway“. Die Lense erklärt
   Symbole, wo der Name allein nicht reicht: `/&` (ursprünglich HF↔VHF-Gateway, heute meist
   iGates; sauberer wären Overlays I&, R&, T&, 2&), Digipeater-Overlays (1# Fill-in, S# regional,
   I# mit iGate …), Gateway-Overlays, `/_`, `/r`, `/-`.
- Nebenbei: PARM/UNIT/EQNS zeigen ihre Werte jetzt Kanal für Kanal (A1 Volt · A2 Pkt …), lange
  Werte brechen in der Lense um.
- Tests in `tests/test_aprs.py`. Client-Version 2026.10.16.3.
