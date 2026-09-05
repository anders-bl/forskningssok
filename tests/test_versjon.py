"""Verifiserer versjon.py: at byggnummeret faktisk følger koden, og at det ikke følger
noe det ikke skal.

Poenget med testene er ikke at hashen «returnerer noe» — det er at den har de to
egenskapene den finnes for: den endrer seg når kjørende kode endres, og den endrer seg
IKKE når noe utenfor kjørende kode endres.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import versjon  # noqa: E402


def _bygg_i(rot: Path) -> str:
    """Beregner byggnummeret som om `rot` var repoet."""
    gammel = versjon._ROT
    try:
        versjon._ROT = rot
        return versjon._bygg()
    finally:
        versjon._ROT = gammel


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "adapters").mkdir()
    (tmp_path / "profiler").mkdir()
    (tmp_path / "frontend").mkdir()
    (tmp_path / "api.py").write_text("app = 1\n")
    (tmp_path / "adapters" / "kilde.py").write_text("def sok(): ...\n")
    (tmp_path / "profiler" / "fag.toml").write_text('navn = "Fag"\n')
    (tmp_path / "frontend" / "index.html").write_text("<h1>hei</h1>")
    return tmp_path


def test_byggnummeret_er_stabilt_for_uendret_kode(tmp_path):
    r = _repo(tmp_path)
    assert _bygg_i(r) == _bygg_i(r)


def test_byggnummeret_endres_naar_koden_endres(tmp_path):
    r = _repo(tmp_path)
    for fil in ("api.py", "adapters/kilde.py", "profiler/fag.toml", "frontend/index.html"):
        før = _bygg_i(r)
        sti = r / fil
        sti.write_text(sti.read_text() + "\n# endret\n")
        assert _bygg_i(r) != før, f"{fil} er kjørende kode og MÅ telle med"


def test_navnebytte_alene_endrer_byggnummeret(tmp_path):
    """Samme innhold under et annet navn er en annen utgave. Uten at filnavnet hashes
    sammen med innholdet ville de to vært umulige å skille."""
    r = _repo(tmp_path)
    før = _bygg_i(r)
    (r / "adapters" / "kilde.py").rename(r / "adapters" / "annen_kilde.py")
    assert _bygg_i(r) != før


def test_versjon_py_teller_IKKE_med(tmp_path):
    """Ellers ville en ren VERSJON-bump endret byggnummeret uten at én kjørende linje ble
    annerledes — og tallet ville sluttet å bety «denne koden»."""
    r = _repo(tmp_path)
    før = _bygg_i(r)
    (r / "versjon.py").write_text('VERSJON = "9.9.9"\n')
    assert _bygg_i(r) == før


def test_testene_teller_IKKE_med(tmp_path):
    """tests/ er ekskludert fra imaget (.dockerignore). Talte de med, ville samme kjørende
    kode fått ulikt byggnummer lokalt og i prod — nøyaktig forvirringen tallet skal fjerne."""
    r = _repo(tmp_path)
    (r / "tests").mkdir()
    før = _bygg_i(r)
    (r / "tests" / "test_noe.py").write_text("def test_x(): assert True\n")
    assert _bygg_i(r) == før


def test_uleselig_rot_gir_ukjent_ikke_et_krasj(tmp_path):
    """Et byggnummer er diagnostikk. At det ikke kan beregnes skal aldri hindre appen i å
    starte — da ville sporingsmekanismen tatt ned det den skulle spore."""
    from unittest.mock import patch
    r = _repo(tmp_path)
    with patch.object(Path, "read_bytes", side_effect=OSError("disk borte")):
        assert _bygg_i(r) == "ukjent"


def test_info_baerer_alle_tre_feltene():
    i = versjon.info()
    assert set(i) == {"versjon", "bygg", "tagline"}
    assert i["versjon"].count(".") == 2, "semantisk versjon, ikke et løpenummer"
    assert i["tagline"]


def test_offentlig_helse_lekker_ikke_versjonen():
    """/health uten nøkkel skal si status og ingenting annet — også nå som detaljen har
    fått version/releaseId. Samme kontrakt som test_helse_lekker_ingen_tall_uten_noekkel,
    men for de nye feltene."""
    import api
    from fastapi.testclient import TestClient
    r = TestClient(api.app).get("/health")
    assert set(r.json()) == {"status"}
    assert versjon.BYGG not in r.text and versjon.VERSJON not in r.text
