"""Verifiserer ai_assistent.py sin mønstergjenkjenning — spesielt at den faktisk finner
noe i et korpus som overveiende er ENGELSK. De opprinnelige mønstrene var rene bokmåls-ord
("signifikant", "korrelerer" …) og traff kun 7 % av 191 ekte cachede abstracts (målt
2026-09-10) — nesten alt via en tilfeldig delstreng-krasj ("identifi*"), ikke ved design.
Nå brukt fra to steder (ai_assistent.py sin CLI OG api.py sin /api/rapport/konvergens),
så regresjon her rammer begge.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ai_assistent  # noqa: E402
import bank  # noqa: E402
from schemas import PaperDossier  # noqa: E402


def _p(tittel, abstract):
    return {"id": tittel, "tittel": tittel, "abstract": abstract, "forfattere": "A. Forfatter",
            "aar": 2024, "doi": None}


def test_engelsk_abstract_med_signifikant_resultat():
    p = _p("Et engelsk funn", "The treatment group showed a significant improvement (p<0.05).")
    funn = ai_assistent.detekter_hovedfunn([p])
    assert any(f["type"] == "signifikant" for f in funn)


def test_engelsk_abstract_med_deteksjon():
    p = _p("En engelsk metode", "This method can detect early-stage lesions reliably.")
    funn = ai_assistent.detekter_hovedfunn([p])
    assert any(f["type"] == "deteksjon" for f in funn)


def test_engelsk_abstract_med_korrelasjon():
    p = _p("En engelsk sammenheng", "Elevated CO2 was associated with reduced growth rates.")
    funn = ai_assistent.detekter_hovedfunn([p])
    assert any(f["type"] == "korrelasjon" for f in funn)


def test_norsk_abstract_fungerer_fortsatt():
    """Regresjonsvakt: de opprinnelige bokmåls-mønstrene skal ikke ha forsvunnet i
    utvidelsen til engelsk."""
    p = _p("Et norsk funn", "Studien fant at stress signifikant påvirker veksten hos fisken.")
    funn = ai_assistent.detekter_hovedfunn([p])
    typer = {f["type"] for f in funn}
    assert "signifikant" in typer and "korrelasjon" in typer


def test_ett_papir_kan_treffe_flere_moenstre():
    p = _p("Alt på en gang", "This significant, correlated finding helped detect the cause.")
    funn = ai_assistent.detekter_hovedfunn([p])
    typer = {f["type"] for f in funn}
    assert typer == {"signifikant", "deteksjon", "korrelasjon"}


def test_hvert_funn_baerer_kildepapiret():
    """detekter_hovedfunn skal ALDRI returnere en løsrevet påstand — samme prinsipp
    som resten av huset (rapport.py bygger kilde-lenken fra nettopp dette feltet)."""
    p = _p("Kildesporbarhet", "This is a significant result.")
    funn = ai_assistent.detekter_hovedfunn([p])
    assert funn[0]["papir"] is p


def test_ingen_moenstre_gir_aerlig_tom_liste():
    p = _p("Ingenting å hente", "Salmon were fed a standard commercial diet for twelve weeks.")
    assert ai_assistent.detekter_hovedfunn([p]) == []


def test_tomt_eller_manglende_abstract_krasjer_ikke():
    ut = ai_assistent.detekter_hovedfunn([_p("Uten abstract", ""), {"id": "x", "tittel": "Uten felt"}])
    assert ut == []


class TestHentFraCache:
    """Regresjonsvakt for CLI-veien (--svar): brukte til 2026-09-10 en default db_path
    på «bank.db» (fantes aldri) OG en SQL-spørring mot en «kilde»-kolonne som aldri har
    eksistert i papers-tabellen (den ekte kolonnen er kilde_kode) — CLI-en rapporterte
    derfor ALLTID «ingen studier funnet», selv med hundrevis av ekte cachede papirer,
    uten at noe fanget det (ai_assistent.py ble aldri kjørt mot en ekte-skjema-db i
    testsuiten, kun detekter_hovedfunn ble testet). Bygger derfor db-en via bank.lagre()
    her — den EKTE skjema-oppretteren — ikke en hånd-skrevet CREATE TABLE som selv kunne
    drevet fra virkeligheten."""

    def _lagre(self, db_path, **felter):
        felter.setdefault("pmid", None)
        felter.setdefault("doi", "10.1234/test")
        felter.setdefault("forfattere", "Testesen T")
        felter.setdefault("tidsskrift", "Test Journal")
        felter.setdefault("aar", 2024)
        felter.setdefault("abstract", "en testabstract om laks")
        felter.setdefault("siteringstall", 0)
        felter.setdefault("open_access", False)
        felter.setdefault("kilde_url", "https://example.org/test")
        bank.lagre([PaperDossier(**felter)], db_path=db_path)

    def test_finner_ekte_lagret_papir_uten_sql_feil(self, tmp_path):
        db_path = tmp_path / "cache.db"
        self._lagre(db_path, tittel="Laks og lever", kilde_kode="MED")
        treff = ai_assistent.hent_fra_cache("laks", db_path)
        assert len(treff) == 1
        assert treff[0]["tittel"] == "Laks og lever"

    def test_ingen_db_gir_aerlig_tom_liste(self, tmp_path):
        assert ai_assistent.hent_fra_cache("laks", tmp_path / "finnes-ikke.db") == []


class TestGrupperEtterKilde:
    """kilde_kode er Europe PMC sin EGNE kildekode (MED/AGR/PPR …), ikke et
    visningsnavn — samme klassifisering som frontend/index.html sin kildeGruppe():
    alt som ikke er CORE/OpenAlex er Europe PMC, uansett hvilken av Europe PMC sine
    egne kildekoder det er (ingen uttømmende liste å holde synkron to steder)."""

    @staticmethod
    def _papir(kilde):
        return {"id": kilde, "kilde": kilde}

    def test_med_agr_ppr_grupperes_alle_som_europe_pmc(self):
        grupper = ai_assistent.grupper_etter_kilde(
            [self._papir("MED"), self._papir("AGR"), self._papir("PPR")])
        assert set(grupper.keys()) == {"PubMed/Europe PMC"}
        assert len(grupper["PubMed/Europe PMC"]) == 3

    def test_core_og_openalex_holdes_atskilt(self):
        grupper = ai_assistent.grupper_etter_kilde(
            [self._papir("CORE"), self._papir("OpenAlex"), self._papir("MED")])
        assert set(grupper.keys()) == {"CORE", "OpenAlex", "PubMed/Europe PMC"}
