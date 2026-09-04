"""Verifiserer domeneprofil.py isolert — ranking.py/scoping.py sine egne tester
(test_ranking.py, test_scoping.py) dekker allerede at de re-eksporterer riktig, dette
dekker kun selve substreng-matchen som nå bor her."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from domeneprofil import AKSER, arts_naer_tekst, domene_naer_tekst  # noqa: E402


def test_domene_naer_tekst_matcher_norsk_fagmiljoe():
    assert domene_naer_tekst("Ola Nordmann, Havforskningsinstituttet")


def test_domene_naer_tekst_matcher_fagtidsskrift():
    assert domene_naer_tekst("Jane Doe, Journal of Fish Diseases")


def test_domene_naer_tekst_urelatert_gir_false():
    assert not domene_naer_tekst("Jane Doe, MIT, Nature")


def test_domene_naer_tekst_tom_streng_gir_false_ikke_feil():
    assert not domene_naer_tekst("")
    assert not domene_naer_tekst(None)


def test_akser_har_forventede_navn():
    assert set(AKSER.keys()) == {"Faser", "Miljøfaktorer", "Regenerasjon", "Lever", "Ultralyd-validering"}


def test_arts_naer_tekst_finner_maalart():
    assert arts_naer_tekst("Nephrocalcinosis in farmed Atlantic salmon")
    assert arts_naer_tekst("En norsk tekst om laks i oppdrett")


def test_arts_naer_tekst_ekte_species_trap_caset_gir_false():
    """Den faktiske tittelen som trigget funnet 2026-09-02 — ingen fisketerm i det hele
    tatt, kun delt nøkkelord (nephrocalcinosis) med fiskedomenet."""
    tittel = "Late onset presentation of nephrocalcinosis and nephrolithiasis in association with a heterozygous CYP24A1 pathogenic variant"
    assert not arts_naer_tekst(tittel)


def test_arts_naer_tekst_salmon_calcitonin_er_ikke_en_fisketreff():
    """Ekte falsk-positiv fanget live 2026-09-02: «salmon calcitonin» er et legemiddel-
    navn i kalsium-/nyrestein-litteraturen (kalsitonin isolert fra laks opprinnelig),
    ikke et signal om at teksten faktisk handler om fisk."""
    tekst = ("CYP24A1 and SLC34A1 mutations in five cases with idiopathic infantile "
             "hypercalcemia. Patients were treated with salmon calcitonin injection.")
    assert not arts_naer_tekst(tekst)


def test_arts_naer_tekst_ekte_salmon_term_fortsatt_matcher_ved_siden_av_calcitonin():
    """Fjerningen av «salmon calcitonin» skal ikke skjule et EKTE fiskefunn som også
    nevner legemidlet et annet sted i teksten."""
    tekst = "Nephrocalcinosis in Atlantic salmon treated experimentally with salmon calcitonin"
    assert arts_naer_tekst(tekst)


def test_arts_naer_tekst_tom_streng_gir_false_ikke_feil():
    assert not arts_naer_tekst("")
    assert not arts_naer_tekst(None)


# ---------- MeSH-predikatet: tre utfall, ikke to (2026-09-04) ----------

def test_mesh_predikatet_har_tre_utfall():
    """«Ikke indeksert» er en ANNEN tilstand enn «indeksert og ikke om målarten».
    41 av 55 cachede papirer har ingen MeSH — preprints, CORE-treff og tidsskrifter
    utenfor MEDLINE. Å svare False for dem ville vært å utlede fravær av INDEKSERING til
    fravær av ART, altså samme tre-utfalls-feil huset jakter på ellers."""
    from domeneprofil import arts_naer_mesh
    assert arts_naer_mesh(("Salmo salar", "Fish Diseases")) is True
    assert arts_naer_mesh(("Humans", "Hypercalcemia", "Calcitonin")) is False
    assert arts_naer_mesh(()) is None
    assert arts_naer_mesh("") is None
    assert arts_naer_mesh(None) is None
    assert arts_naer_mesh("|||") is None, "tomme rør-felt er heller ikke en indeksering"


def test_mesh_predikatet_leser_roerseparert_fra_cachen():
    from domeneprofil import arts_naer_mesh
    assert arts_naer_mesh("Animals|Salmo salar|Fish Diseases") is True


def test_mesh_feller_salmon_calcitonin_kollisjonen():
    """Positiv kontroll, kjørt FØR eksperimentets dom ble lest. Er dette tilfellet ikke
    felt, er predikatet galt og målingen måler instrumentet."""
    from domeneprofil import arts_naer_mesh
    human = ("Humans", "Infant", "Hypercalcemia", "Calcitonin",
             "Vitamin D3 24-Hydroxylase", "Nephrocalcinosis")
    assert arts_naer_mesh(human) is False


def test_animals_alene_er_ikke_et_artstreff():
    """«Animals» står på nesten alle dyrestudier, også humanmedisinske musemodeller.
    Den er bevisst utelatt fra profilens mesh_termer — med den ville predikatet vært
    nesten alltid sant, og et predikat som alltid er sant måler ingenting."""
    from domeneprofil import arts_naer_mesh
    assert arts_naer_mesh(("Animals", "Mice", "Hypercalcemia")) is False


def test_stedsnavn_er_ikke_et_artstreff():
    """«Salmon Arm» er en by i British Columbia. Funnet ved korpus-inspeksjon 2026-09-04:
    «A Salmon Arm scrapbook» lå i cachen med arts_naer=True og ble båndet OPP over ekte
    fiskehelse-papirer. Samme homonym-klasse som legemiddelnavnet «salmon calcitonin»."""
    from domeneprofil import arts_naer_tekst
    assert arts_naer_tekst("A Salmon Arm scrapbook") is False
    assert arts_naer_tekst("Nephrocalcinosis in farmed salmon") is True


def test_lakseokonomi_forblir_et_artstreff_og_det_er_riktig():
    """Kalibreringens viktigste funn: seks lakseøkonomi-papirer i cachen er IKKE falske
    positive for arts_naer. De handler faktisk om laks. Predikatet svarer korrekt på sitt
    eget spørsmål — «nevner dette målarten?» — og problemet er at å NEVNE laks ikke er det
    samme som å handle om laksens HELSE.

    Det er en manglende dimensjon i domeneprofilen (fagfelt), ikke en feil i artsaksen, og
    en kollisjonsfrase kan ikke fikse det: «salmon» står med rette i tittelen."""
    from domeneprofil import arts_naer_tekst
    assert arts_naer_tekst("Economic Factors Effecting Salmon Fisheries in Japan") is True
