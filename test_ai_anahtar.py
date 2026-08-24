# -*- coding: utf-8 -*-
"""AI okuyucu: donusumlu anahtar + kota durum bildirimi.

NEDEN: kullanici ikinci bir Gemini anahtari verip "bir onceki ile donusumlu
kullanabilir misin" dedi — iki anahtar paylasilinca kota iki katina cikar.
Ayrica: 429 (kota) hatasi TEK bir parcada olup BASKA anahtarla kurtarilirsa
calisma BASARILI sayilmali (SON_DURUM sifirlanmali); TUM anahtarlar
tukenirse HIZLICA vazgecilmeli (dakikalarca tek tek denenmemeli).

Calistirmak icin:  python test_ai_anahtar.py
"""
import importlib.util
import time
import urllib.error
import numpy as np

_s = importlib.util.spec_from_file_location("ai", "ai_okuyucu.py")
_m = importlib.util.module_from_spec(_s)
_s.loader.exec_module(_m)


def _hazirla():
    _m.ayar_oku = lambda: {"saglayici": "gemini", "anahtarlar": ["AAA", "BBB"], "anahtar": "AAA"}
    _m.KARE, _m.ORTUSME = 300, 50
    _m.BEKLE = 0.01


def test_bir_anahtar_kota_diger_kurtarir():
    _hazirla()
    cagrilar = []

    def sahte(b64, ayar, anahtar=None):
        cagrilar.append(anahtar)
        if len(cagrilar) == 2:
            raise urllib.error.HTTPError("u", 429, "quota", {}, None)
        return '[{"deger": "45", "x": 10, "y": 10}]'

    _m._gemini = sahte
    im = np.full((700, 700), 255, dtype="uint8")
    sonuc = _m.olculeri_oku(im)
    assert len(set(cagrilar)) == 2, "iki anahtar da kullanilmadi: %r" % cagrilar
    assert len(sonuc) >= 1, "kurtarilan tur sonuc uretmedi"
    assert _m.SON_DURUM == "tamam", "429'dan kurtulunca SON_DURUM tamam olmali"


def test_tum_anahtarlar_tukenince_hizli_vazgecer():
    _hazirla()

    def sahte(b64, ayar, anahtar=None):
        raise urllib.error.HTTPError("u", 429, "quota", {}, None)

    _m._gemini = sahte
    im = np.full((700, 700), 255, dtype="uint8")
    t0 = time.time()
    sonuc = _m.olculeri_oku(im)
    sure = time.time() - t0
    assert sonuc == [] and _m.SON_DURUM == "kota"
    assert sure < 5, "tum anahtarlar tukenince HEMEN vazgecmeli (%.1f sn surdu)" % sure


if __name__ == "__main__":
    test_bir_anahtar_kota_diger_kurtarir()
    test_tum_anahtarlar_tukenince_hizli_vazgecer()
    print("ai anahtar testleri: TAMAM")
