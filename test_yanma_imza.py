# -*- coding: utf-8 -*-
"""TL 1010 yanma raporu: imza gorselleri satir kaydirmayla BIRLIKTE taşınır.

NEDEN: numune blogu 3'ten 5'e cikarilirken satirlar 12 kaydiriliyor, ama
IMZA TARAMALARI (Umut Ciftciogullari / Volkan Pekatik gercek imza gorselleri)
worksheet XML'inde DEGIL, AYRI bir drawing XML'inde hucre koordinatina
capalanmis. Satir kaydirmasi bu XML'e dokunmayinca imzalar ESKI KONUMDA
KALDI ve YENI 4. numune blogunun UZERINE BINDI (kullanici: "imzalar
daralmis ve yeri kaymis").

Calistirmak icin:  python test_yanma_imza.py
"""
import importlib.util

_s = importlib.util.spec_from_file_location("ag", "apqp_belge_uret.py")
_m = importlib.util.module_from_spec(_s)
_s.loader.exec_module(_m)

# Gercek drawing1.xml yapisi: iki imza, 0-tabanli satir 39 (=Excel satir 40)
CIZIM = (
    '<xdr:wsDr><xdr:twoCellAnchor>'
    '<xdr:from><xdr:col>4</xdr:col><xdr:row>39</xdr:row></xdr:from>'
    '<xdr:to><xdr:col>5</xdr:col><xdr:row>39</xdr:row></xdr:to>'
    '</xdr:twoCellAnchor><xdr:twoCellAnchor>'
    '<xdr:from><xdr:col>9</xdr:col><xdr:row>39</xdr:row></xdr:from>'
    '<xdr:to><xdr:col>12</xdr:col><xdr:row>39</xdr:row></xdr:to>'
    '</xdr:twoCellAnchor></xdr:wsDr>')


def test_imza_capalari_kaydirilir():
    # esik 0-tabanli 37 (=Excel 38, "Tests carried out" satiri), kaydir 12
    yeni = _m._cizim_satirlari_kaydir(CIZIM, 37, 12)
    assert "<xdr:row>51</xdr:row>" in yeni, "imza capasi kaydirilmadi"
    assert "<xdr:row>39</xdr:row>" not in yeni, "eski satir kaldi"


def test_esigin_ustundeki_capalar_dokunulmaz():
    """Numune bloklarindaki (esigin USTUNDE) gorseller KAYDIRILMAMALI."""
    ust = CIZIM.replace("<xdr:row>39</xdr:row>", "<xdr:row>20</xdr:row>")
    yeni = _m._cizim_satirlari_kaydir(ust, 37, 12)
    assert "<xdr:row>20</xdr:row>" in yeni, "esigin ustundeki capa yanlislikla kaydirildi"


def test_sayfa_cizim_yolu_bulunur():
    import os
    kaynak = os.path.join(_m.PPAP_KLASOR, "Flammability Test Report VW.xlsx")
    if not os.path.exists(kaynak):
        return                                     # sablon yoksa test atlanir
    sayfa = _m.ilk_sayfa_yolu(kaynak)
    yol = _m._sayfa_cizim_yolu(kaynak, sayfa)
    assert yol and yol.endswith(".xml"), "cizim yolu bulunamadi: %r" % yol


if __name__ == "__main__":
    test_imza_capalari_kaydirilir()
    test_esigin_ustundeki_capalar_dokunulmaz()
    test_sayfa_cizim_yolu_bulunur()
    print("yanma imza testleri: TAMAM")
