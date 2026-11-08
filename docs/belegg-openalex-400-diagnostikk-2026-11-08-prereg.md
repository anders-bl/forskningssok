# Prereg: diagnostikk av OpenAlex 400 i Belegg-siteringsprobe

Tidspunkt: 2026-11-08, etter resultatcommit `f4e501876705c984e369747fcb9978da1f4d54fc`
og for de diagnostiske API-kallene.

## Formal

Isolere hvilken parameter eller endepunktkombinasjon som utloser HTTP 400 i den
eksisterende OpenAlex `siterende_verk`-adapteren. Dette er feildiagnostikk, ikke en ny
sokedeknings- eller kvalitetsmaling.

## Frosne kall

Bruk den allerede kjente offentlige seed-ID-en `W7128841028` og kall `/works` med
`filter=cites:W7128841028`, `per_page=20`. Utfor disse variantene, ett parameterledd
av gangen:

1. `sort=-publication_date`, `cursor=*`, og adapterens `select`-liste.
2. Som 1, men uten `select`.
3. Som 1, men uten `sort`.
4. Som 1, men uten `cursor`.
5. Bare filter og `per_page`.

For hvert kall bevar status og responsens valideringsmelding. Ved 200 bevar kun antall
treff og de tre forste ID/tittel-parene. Ikke skriv ut eller lagre API-nokkel.

## Tolkning

- Feil som forsvinner nar ett felt fjernes peker pa dette feltet eller kombinasjonen,
  men krever oppfolgende isolering for rotarsak.
- Hvis variant 5 feiler, merk `kunne ikke maales` for adapterdiagnosen; ikke tilskriv
  feilen en bestemt parameter.
- Ingen variantutfall kan brukes som evidens for at OpenAlex mangler artikler.

