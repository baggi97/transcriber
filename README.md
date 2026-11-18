# Transskriber

En lille Mac-app, der laver dansk tekst ud fra lydfiler. Træk en lydfil ind i vinduet, og få et Word-dokument. Alt kører lokalt på Macen (Whisper via `mlx-whisper`), så lyden forlader aldrig computeren.

Kræver en Mac med Apple-chip (M1 eller nyere).

## Indhold

```
transskriber/
├─ install.sh            Installerer (og opdaterer) programmet
├─ config.env            Repo-navn og sprogmodel (ét sted, bruges af alt)
├─ VERSION               Versionsnummer, fx 1.0.0
├─ requirements.txt      Python-pakker
├─ app/transskriber.py   Selve programmet
├─ assets/icon1024.png   Ikon
└─ scripts/              Afinstaller- og motoropdaterings-scripts
```

## Opsætning (gøres én gang)

1. Opret et **offentligt** repo på GitHub, fx `transskriber`.
   (Offentligt, så appen kan tjekke for opdateringer uden login.)
2. Læg alle filerne herfra i repoet.
3. Åbn `config.env` og ret linjen `GITHUB_REPO` til dit eget navn, fx `baggi97/transcriber`.
4. Commit og push.
5. Udgiv den første version, se næste afsnit (tag `v1.0.0`, som svarer til `VERSION`).

## Installere på en Mac

1. På repoets GitHub-side: **Code → Download ZIP**, og pak ud.
2. Åbn Terminal i den udpakkede mappe og kør:

   ```bash
   bash install.sh
   ```

3. Vent til den siger "Færdig". Programmet ligger nu i `~/Applications/Transskriber.app`. Træk det ned i Dock'en.

Har Macen en ældre installation fra det gamle `installer.sh`, så kør bare `install.sh` herfra én gang. Derefter kan appen opdatere sig selv.

## Udgive en ny version

1. Ret koden, og læg versionsnummeret op i filen `VERSION` (fx `1.0.1`).
2. Commit og push.
3. På GitHub: **Releases → Draft a new release**.
   - **Tag:** `v` + versionsnummeret, fx `v1.0.1` (skal være højere end den forrige).
   - Skriv gerne et par linjer om, hvad der er nyt. Det vises i appen, før man opdaterer.
   - Tryk **Publish release**.

Det er først, når du udgiver en release, at brugerne kan se opdateringen. Du kan altså pushe og rode i `main`, uden at nogen påvirkes. Kladder og pre-releases ignoreres, så de er gode til at teste.

## Sådan virker opdateringen

- Appen spørger GitHub efter den nyeste release, når den starter, og derefter hver 6. time.
- Er der en nyere, vises *"Ny version … – Opdater nu"* nederst i vinduet.
- Først når brugeren trykker og bekræfter, henter appen releasen, kører `install.sh` fra den og starter forfra.
- Går noget galt (ingen internet, ugyldig release, fejl i installationen), vises en fejlbesked, og den gamle version bliver i brug. Loggen ligger i
  `~/Library/Application Support/Transskriber/update.log`.

## Sikkerhed

Opdateringen kører `install.sh` fra dine releases. Den, der kan udgive en release på din GitHub-konto, kan altså få kode til at køre på brugernes Mac. Slå derfor to-faktor-login til på kontoen. Appen opdaterer aldrig uden, at brugeren trykker "Opdater nu".

## Fejlfinding: der kommer ingen opdateringsbesked

- Er repoet offentligt?
- Står det rigtige navn i `GITHUB_REPO` i `config.env`, i den *installerede* version? Ligger den på Macen i `~/Library/Application Support/Transskriber/config.env`.
- Er releasen udgivet (ikke en kladde eller pre-release)?
- Er release-tagget et højere versionsnummer end det installerede? (Versionen vises i vinduets titel.)
- GitHub begrænser antallet af tjek pr. time pr. IP-adresse. På et delt netværk kan et tjek derfor fejle, og så prøver appen igen senere.

## Vedligeholdelse

| Hvad | Kommando |
|------|----------|
| Opdatere motoren (mlx-whisper m.m.) | `bash "$HOME/Library/Application Support/Transskriber/Opdater.command"` |
| Fjerne alt igen | `bash "$HOME/Library/Application Support/Transskriber/Afinstaller.command"` |

Lavet af Rasmus Lolk Andersen.
