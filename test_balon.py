# -*- coding: utf-8 -*-
"""Balonlama: hayalet okuma korumasi + AI kotasi durum bildirimi.

NEDEN: kullanici 700.0.454 ciziminde metinsiz BOS alana dusen bir "hayalet"
balon gordu (30 numarali balon, R15 kosesinde). Kok sebep: model kutu
eslesmesi bulamayinca ham konumunu HIC DOGRULAMADAN kabul ediyorduk. Ayrica
AI kotasi (429) tukendiginde eskiden her parcayi tek tek deneyip dakikalarca
ugrasiyor, sonra da KLASIK OCR'A dusup not blogundaki metne cop balon
basiyordu.

Calistirmak icin:  python test_balon.py
"""
import importlib.util
import numpy as np
import cv2

_s = importlib.util.spec_from_file_location("bl", "balonla.py")
_m = importlib.util.module_from_spec(_s)
_s.loader.exec_module(_m)


def test_bos_alanda_hayalet_okuma_atilir():
    im = np.full((400, 400), 255, dtype=np.uint8)
    assert _m._konumda_yazi_var_mi(im, 200, 200) is False


def test_yazili_alanda_okuma_korunur():
    im = np.full((400, 400), 255, dtype=np.uint8)
    cv2.putText(im, "45", (170, 210), cv2.FONT_HERSHEY_SIMPLEX, 1.4, 0, 3)
    assert _m._konumda_yazi_var_mi(im, 200, 200) is True


def test_ai_olculeri_hayalet_okumayi_atar():
    import ai_okuyucu
    im = np.full((600, 600), 255, dtype=np.uint8)
    cv2.putText(im, "45", (270, 310), cv2.FONT_HERSHEY_SIMPLEX, 1.4, 0, 3)

    def sahte_oku(im, log=None):
        return [("45", 280, 300), ("30", 100, 100)]      # ikincisi bos kosede

    esk = ai_okuyucu.olculeri_oku
    ai_okuyucu.olculeri_oku = sahte_oku
    try:
        sonuc = _m._ai_olculeri(im, [45.0])
    finally:
        ai_okuyucu.olculeri_oku = esk
    degerler = [o[0] for o in sonuc]
    assert "45" in degerler and "30" not in degerler, "hayalet balon SUZULMEDI: %r" % degerler


if __name__ == "__main__":
    test_bos_alanda_hayalet_okuma_atilir()
    test_yazili_alanda_okuma_korunur()
    test_ai_olculeri_hayalet_okumayi_atar()
    print("balon testleri: TAMAM")
