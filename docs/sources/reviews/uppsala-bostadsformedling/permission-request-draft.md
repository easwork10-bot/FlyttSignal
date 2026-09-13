# Draft — permission request for public rental-listing data

This draft requests permission; it does not assume that public pages may be automated. Replace the bracketed organisation details before sending it to Uppsala Bostadsförmedling.

## Suggested subject

Förfrågan om tillstånd eller läs-API för begränsad användning av publika bostadsannonser

## Suggested message

Hej,

Vi utvecklar FlyttSignal, en intern prototyp för att analysera förändringar i bostadsutbudet i Uppsala. Vi vill fråga om skriftligt tillstånd att maskinellt läsa ett begränsat urval av de publika bostadsannonserna på bostad.uppsala.se, eller om ni har ett dokumenterat läs-API/partnergränssnitt som vi bör använda i stället.

Det föreslagna användningssättet är:

- högst en komplett hämtning per dygn, med låg samtidighet, tydlig user-agent, timeout, backoff och omedelbar avstängningsmöjlighet;
- endast publika annonsfält såsom annons-/objektnummer, kanonisk URL, adress, bostadstyp, storlek, antal rum, hyra, publicerings-/ansöknings-/inflyttningsdatum och publik status;
- inga sökande-, kö-, hyresgäst-, kontakt- eller andra personuppgifter;
- rå HTML sparas i högst 30 dagar för teknisk felsökning och spårbarhet;
- strukturerade, icke-personliga annons- och livscykelobservationer sparas i högst 12 månader för intern analys;
- inga annonser, bilder eller fullständiga dataflöden återpubliceras eller säljs vidare;
- endast interna, aggregerade eller förklarbara indikatorer visas;
- en försvunnen annons tolkas aldrig automatiskt som uthyrd och kräver minst två fullständiga, lyckade hämtningar innan den markeras som borttagen.

Vi implementerar ingenting mot er webbplats innan vi fått ett uttryckligt godkännande. Om ni föredrar ett API eller annan teknisk leverans följer vi gärna den vägen.

Kan ni bekräfta:

1. om användningen ovan är tillåten;
2. om det finns ett läs-API eller partnergränssnitt för publika annonser;
3. tillåten frekvens, samtidighet och identifiering av klienten;
4. vilka fält, lagringstider och former av intern presentation som är godkända;
5. krav på källhänvisning, rättelse, radering eller avstängning.

Vänliga hälsningar,

`[NAMN]`<br>
`[ORGANISATION]`<br>
`[E-POST]`<br>
`[TELEFON, VALFRITT]`

## Decision handling

Save the complete written response in this review directory. Update the registry with the approved interface, fields, limits, retention and redistribution terms. A positive but ambiguous answer remains `WAIT` until the operational details are explicit.
