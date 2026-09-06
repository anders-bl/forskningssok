// rapport_mal.typ — Fjordstein-malen for alle PDF-rapporter (husstandard rapportgenerering,
// prosesser/husstandard-rapportgenerering). Dette er det ENE stedet merkevare og typografi
// bor for PDF; rapport.py sender bare innhold som strenger, aldri layout.
//
// Fontvalg: Libertinus Serif er innebygd i typst-binæren, så malen gir samme utseende i
// python:3.14-slim (ingen systemfonter) som på en Mac. Fjordsteins system-font-stack er en
// SKJERM-beslutning (null webfont = gratis LCP); på papir er en serif med ekte kursiv og
// gamle tall riktigere, og «ingen nedlasting» gjelder her også: fonten følger binæren.
//
// Tekst kommer inn som string-argumenter (rapport.py escaper kun \ og "), ALDRI som
// Typst-markup: en tittel med # eller * i seg skal rendres bokstavelig, ikke tolkes.

#let aksent = rgb("#2E5C47")   // Fjordstein --accent (lys modus)
#let dempet = rgb("#5A5A56")   // Fjordstein --text-muted (lys modus)
#let strek = rgb("#E5E4E0")    // Fjordstein --border

#let rapport(tittel: "", dato: "", body) = {
  set page(
    paper: "a4",
    margin: (top: 22mm, bottom: 22mm, left: 22mm, right: 22mm),
    footer: context [
      #set text(size: 8pt, fill: dempet)
      #grid(
        columns: (1fr, auto),
        [av Lauvasdata #sym.dot.c #tittel],
        [#counter(page).display("1 / 1", both: true)],
      )
    ],
  )
  set text(font: "Libertinus Serif", size: 10.5pt, lang: "nb")
  set par(justify: false, leading: 0.62em, spacing: 0.9em)
  body
}

#let h1(t) = {
  block(below: 0.4em, text(size: 20pt, weight: "bold", fill: aksent, t))
}

#let h2(t) = {
  block(above: 1.4em, below: 0.5em, text(size: 13.5pt, weight: "bold", fill: aksent, t))
}

#let h3(t) = {
  block(above: 1.1em, below: 0.35em, text(size: 11pt, weight: "bold", t))
}

#let meta(t) = {
  block(below: 0.8em, text(size: 9pt, style: "italic", fill: dempet, t))
}

#let p(t) = {
  par(t)
}

// Sitat: innrykk med tynn aksent-strek i margen, dempet kursiv, guillemets.
#let sitat(t) = {
  block(
    inset: (left: 10pt, top: 2pt, bottom: 2pt),
    stroke: (left: 1.5pt + aksent),
    text(style: "italic", fill: dempet, [«#t»]),
  )
}

#let lenke(t) = {
  block(below: 0.6em, text(size: 8.5pt, fill: aksent, link(t, t)))
}

// Tynn strek under tittelblokken, samme farge som --border på skjerm.
#let skille() = {
  block(above: 0.2em, below: 1em, line(length: 100%, stroke: 0.5pt + strek))
}
