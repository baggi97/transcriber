# Vedligeholdelse

Noter til den, der vedligeholder Transskriber og udgiver nye versioner. Brugervejledningen står i [README.md](README.md).

## Indhold

```
hent.sh               Henter nyeste release og kører dens install.sh (bruges af installationslinjen i README)
install.sh            Installerer og opdaterer programmet (kan køres igen og igen)
config.env            Repo-navn og sprogmodel. Læses både af bash og af appen
VERSION               Versionsnummer, fx 1.0.3. Skal passe med release-tagget
requirements.txt      Python-pakker
app/transskriber.py   Selve programmet
assets/icon1024.png   Ikon
scripts/              Afinstaller- og motoropdaterings-scripts
CLAUDE.md             Projektkontekst til Claude Code
```

## Opsætning af repoet

Repoet skal være **offentligt**, så appen kan tjekke for opdateringer uden login. `GITHUB_REPO` i `config.env` skal pege på det (lige nu `baggi97/transcriber`). `config.env` må kun indeholde linjer på formen `NØGLE="værdi"`, fordi både bash og appen læser den.

## Udgive en ny version

1. Ret koden, og læg versionsnummeret op i `VERSION` (fx `1.0.4`).
2. Tjek scripts og kode:

   ```bash
   bash -n install.sh scripts/*.sh
   python3 -m py_compile app/transskriber.py
   ```

3. Commit og push.
4. På GitHub: **Releases → Draft a new release**.
   - **Tag:** `v` + versionsnummeret, fx `v1.0.4`. Det skal være højere end det forrige.
   - Skriv et par linjer om, hvad der er nyt. Det vises i appen, før brugeren opdaterer.
   - Tryk **Publish release**.

Brugerne ser først opdateringen, når releasen er udgivet. Du kan altså pushe til `main` uden, at nogen påvirkes. Kladder og pre-releases ignoreres, så de er gode til at teste.

**Undtagelse: `hent.sh`.** Installationslinjen i README henter `hent.sh` direkte fra `main`, så ændringer i den virker med det samme for nye installationer. Den henter selv altid den nyeste udgivne release, så resten af koden følger stadig releases. Test ændringer i `hent.sh` lokalt (`bash hent.sh`), før du pusher. Repo-navnet står også i `hent.sh`, så ret det dér, hvis repoet flytter.

## Sådan virker opdateringen

- Appen spørger GitHub efter den nyeste release, når den starter, og derefter hver 6. time.
- Er tagget højere end den installerede version (`version.txt`), vises *"Ny version … – Opdater nu"* nederst i vinduet.
- Først når brugeren trykker og bekræfter, henter appen releasens kildekode, kører `install.sh` fra den og starter forfra.
- `install.sh` kopierer programfilerne til sidst. Går noget galt (ingen internet, ugyldig release, fejl i installationen), bliver den gamle version i brug. Loggen ligger i `~/Library/Application Support/Transskriber/update.log`.

## Sikkerhed

Opdateringen kører `install.sh` fra dine releases. Den, der kan udgive en release på GitHub-kontoen, kan altså få kode til at køre på brugernes Mac. Slå derfor to-faktor-login til på kontoen. Appen opdaterer aldrig uden, at brugeren trykker "Opdater nu".

Repoet er offentligt: commit aldrig hemmeligheder, adgangsnøgler, personlige oplysninger eller rigtige lydoptagelser.

## Fejlfinding: der kommer ingen opdateringsbesked

- Er repoet offentligt?
- Står det rigtige navn i `GITHUB_REPO` i den *installerede* `config.env`? Den ligger i `~/Library/Application Support/Transskriber/config.env`.
- Er releasen udgivet (ikke en kladde eller pre-release)?
- Er release-tagget højere end den installerede version? Versionen står i vinduets titel.
- GitHub begrænser antallet af tjek pr. time pr. IP-adresse. På et delt netværk kan et tjek derfor fejle, og så prøver appen igen senere.

## Kendte faldgruber

- **Installation med `sudo`:** Efterlader mapper, som ejes af root. `install.sh` nægter nu at køre som root og viser den præcise `sudo chown`-kommando, hvis den finder sådanne mapper.
- **Rosetta:** Appens opstarts-script er et bash-script, så uden `LSRequiresNativeExecution` i `Info.plist` starter macOS det under Rosetta. Version 1.0.0 og 1.0.1 manglede den indstilling, og deres opdatering fejlede. `install.sh` starter sig selv forfra som Apple-chip-program, hvis den køres under Rosetta.
- **Ældre installationer fra det gamle `installer.sh`:** Kør `install.sh` herfra én gang. Derefter kan appen opdatere sig selv.

## Vedligeholdelse på en Mac

| Hvad | Kommando |
|------|----------|
| Opdatere motoren (mlx-whisper m.m.) | `bash "$HOME/Library/Application Support/Transskriber/Opdater.command"` |
| Fjerne alt igen | `bash "$HOME/Library/Application Support/Transskriber/Afinstaller.command"` |
| Se hvilken version der er installeret | `cat "$HOME/Library/Application Support/Transskriber/version.txt"` |
