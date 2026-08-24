# -*- coding: utf-8 -*-
"""Musteri adi turetme: kontrol plani -> elle girilen -> SEVK kayitlari.

NEDEN: 700.0.450'in kontrol planinda cari_adi TUM satirlarda bos, ama urun
2020'den beri sevk ediliyor. Musteri adi VDA 2, PPA kapagi, FR243, FR215 ve
QTR gibi MUSTERIYE GIDEN belgelere basiliyor — uydurulamaz.
Kullanici "leansys sevklerden bulabilirsin" dedi; sevk kayitlari bunun
GERCEK kaynagi. Grup ici transferler (SANIFOAM GMBH — kendi Alman sirketi,
hacmin %94'u) elenmezse musteri YANLIS cikar.

Calistirmak icin:  python test_musteri.py
"""
import importlib.util

_s = importlib.util.spec_from_file_location("ag", "apqp_belge_uret.py")
_m = importlib.util.module_from_spec(_s)
_s.loader.exec_module(_m)


def test_grup_sirketleri_elenir():
    for ad in ["SANIFOAM GMBH", "SANICAR TURIZM SAN.TIC.LTD.STI.",
               "Sanifoam Endüstri ve Tüketim Ürünleri"]:
        assert _m.GRUP_SIRKET.search(ad), "grup sirketi elenmedi: %s" % ad
    for ad in ["ADIENT Czech Republic s.r.o.", "LEAR CORPORATION MARTORELL SLU",
               "MAN TÜRKIYE A.S.", "MERCEDES BENZ TÜRK A.S."]:
        assert not _m.GRUP_SIRKET.search(ad), "gercek musteri elendi: %s" % ad


def test_sevkten_musteri_bilinen_urunlerde_dogru():
    """Kontrol planinda musterisi ZATEN bilinen urunlerde, sevkten turetilen
    ad AYNI cikmali — yontemin dogrulugunun bagimsiz kaniti."""
    for kod, beklenen in [("700.0.454", "LEAR"), ("205.0.214-C", "MAN")]:
        ad, _ = _m.sevk_musterisi(kod)
        assert beklenen in ad.upper(), "%s icin sevkten %r cikti, %r bekleniyordu" % (
            kod, ad, beklenen)


if __name__ == "__main__":
    test_grup_sirketleri_elenir()
    test_sevkten_musteri_bilinen_urunlerde_dogru()
    print("musteri testleri: TAMAM")
