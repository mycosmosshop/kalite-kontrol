# -*- coding: utf-8 -*-
"""FR86 Gage R&R: alet cozunurlugu ve calisma turu eslesmesi.

NEDEN: kullanici iki sey bildirdi —
  1) "seritmetreyi virgullu yapmissin" — serit metre olcumleri toleranstan
     turetilen 4 ondalik hanede uretiliyordu (14.9638 mm), hicbir insan bir
     serit metreyi bu hassasiyette okuyamaz.
  2) "terazi dolmamis" — FR86'nin Terazi sayfasi yanlislikla bir PROSES
     YETERLILIGI calismasini (tek operator, 125 satir) MSA calismasi (uc
     operator, 90 satir) yerine secmisti; iki operatorun satirlari boy kaldi.

Calistirmak icin:  python test_msa.py
"""
import importlib.util

_s = importlib.util.spec_from_file_location("ag", "apqp_belge_uret.py")
_m = importlib.util.module_from_spec(_s)
_s.loader.exec_module(_m)


def test_serit_metre_cozunurlugu_gercekci():
    g = {"alet": "Şeritmetre", "tol": 0.6, "dar_alt": 14.8, "dar_ust": 15.4, "dar_nominal": None}
    satir, _ = _m.olcum_uret(g, tohum=134)
    for x in satir:
        metin = str(x["measurement"])
        ondalik = len(metin.split(".")[-1]) if "." in metin else 0
        assert ondalik <= 1, "serit metre 1 ondalikten fazla oldu: %r" % x["measurement"]


def test_serit_metre_kararli_sonuc():
    """Coz. gerceklestirilince ANOVA COKMEMELI (sifira bolme, dev ndc)."""
    g = {"alet": "Şeritmetre", "tol": 0.6, "dar_alt": 14.8, "dar_ust": 15.4, "dar_nominal": None}
    satir, _ = _m.olcum_uret(g, tohum=134)
    _, _, _, kabul, yuz, ndc = _m.anova_grr(satir, g["tol"], 3, 10, 3)
    assert kabul in ("acceptable", "marginal"), "serit metre calismasi RED cikti: %s" % kabul
    assert 0 <= yuz <= 100, "%%GRR mantik disi: %s" % yuz
    assert 0 < ndc < 1000, "ndc kararsiz/dev sayi: %s" % ndc


def test_baska_alet_etkilenmez():
    """Kumpas/mikrometre gibi diger aletler ESKI (tolerans-guduml) davranisi
    korur — yalniz serit metre ozel muamele gorur."""
    g = {"alet": "Kumpas", "tol": 0.6, "dar_alt": 14.8, "dar_ust": 15.4, "dar_nominal": None}
    satir, _ = _m.olcum_uret(g, tohum=134)
    _, _, _, kabul, yuz, ndc = _m.anova_grr(satir, g["tol"], 3, 10, 3)
    assert kabul == "acceptable" and abs(yuz - 6.79) < 0.5 and ndc == 20, (
        "kumpas sonucu degismis olmamali: %s %.2f %d" % (kabul, yuz, ndc))


def test_msa_calismasi_yeterlilik_calismasindan_ayrilir():
    """eslesen_calisma() proses yeterliligi (capability) calismasini degil,
    MSA (type1/2/3) calismasini secmeli — ayni alet adiyla ikisi de olsa da."""
    mevcut = [
        {"id": 141, "study_type": "capability", "study_name": "700.0.454 — Terazi (Ürün Agirligi) Cp/Cpk",
         "study_date": "2025-08-20", "gauge_name": "Terazi", "part_name": "700.0.454"},
        {"id": 135, "study_type": "type2", "study_name": "700.0.454 — Terazi (Ürün Agirligi)",
         "study_date": "2025-08-10", "gauge_name": "Terazi", "part_name": "700.0.454"},
    ]
    secilen = _m.eslesen_calisma({"alet": "Terazi"}, mevcut)
    assert secilen["id"] == 135, "yeterlilik calismasi (141) yanlislikla secildi"


if __name__ == "__main__":
    test_serit_metre_cozunurlugu_gercekci()
    test_serit_metre_kararli_sonuc()
    test_baska_alet_etkilenmez()
    test_msa_calismasi_yeterlilik_calismasindan_ayrilir()
    print("msa testleri: TAMAM")
