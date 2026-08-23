# -*- coding: utf-8 -*-
"""imza_yinelenmesin: yinelenen Relationship Id'yi onler.

NEDEN BU TEST VAR: sablon klasorundeki FR182 ve FR90 dosyalarina bir kez
uretilmis cikti yazilmis; iceride zaten rIdImza var. Uretim ikinci bir kopya
ekleyince rels'te ayni Id iki kez olusuyordu. Yinelenen Id gecersiz OPC'dir ve
Excel o cizimdeki BUTUN resimleri reddediyor — kullanici uc imza yerine uc
"Resim goruntulenemiyor" kutusu goruyordu.

Calistirmak icin:  python test_imza.py
"""
import importlib.util
import re

_s = importlib.util.spec_from_file_location("ag", "apqp_belge_uret.py")
_m = importlib.util.module_from_spec(_s)
_s.loader.exec_module(_m)

KIRLI_CIZIM = (
    '<xdr:wsDr>'
    '<xdr:oneCellAnchor><xdr:from><xdr:col>1</xdr:col><xdr:row>2</xdr:row></xdr:from>'
    '<xdr:pic><xdr:blipFill><a:blip r:embed="rId1"/></xdr:blipFill></xdr:pic></xdr:oneCellAnchor>'
    '<xdr:oneCellAnchor><xdr:from><xdr:col>2</xdr:col><xdr:row>33</xdr:row></xdr:from>'
    '<xdr:pic><xdr:blipFill><a:blip r:embed="rIdImza182"/></xdr:blipFill></xdr:pic></xdr:oneCellAnchor>'
    '</xdr:wsDr>')
KIRLI_RELS = (
    '<Relationships>'
    '<Relationship Id="rId1" Type="image" Target="../media/image1.png"/>'
    '<Relationship Id="rIdImza182" Type="image" Target="../media/imzaUretim182.png"/>'
    '</Relationships>')


def test_kirli_sablon_temizlenir():
    cizim, rels = _m.imza_yinelenmesin(KIRLI_CIZIM, KIRLI_RELS, "rIdImza182")
    assert 'r:embed="rIdImza182"' not in cizim, "eski imza capasi kalmis"
    assert 'Id="rIdImza182"' not in rels, "eski iliski kalmis"
    # Sablonun KENDI imzasina dokunulmaz
    assert 'r:embed="rId1"' in cizim and 'Id="rId1"' in rels, "sablon imzasi silinmis"


def test_temiz_sablon_bozulmaz():
    temiz_c = KIRLI_CIZIM.replace("rIdImza182", "rIdBaska")
    temiz_r = KIRLI_RELS.replace("rIdImza182", "rIdBaska")
    c, r = _m.imza_yinelenmesin(temiz_c, temiz_r, "rIdImza182")
    assert c == temiz_c and r == temiz_r, "ilgisiz icerik degismis"


def test_uretim_sonrasi_id_tek_kalir():
    """Temizlik + yeniden ekleme: Id tam olarak BIR kez bulunmali."""
    cizim, rels = _m.imza_yinelenmesin(KIRLI_CIZIM, KIRLI_RELS, "rIdImza182")
    rels = rels.replace("</Relationships>",
                        '<Relationship Id="rIdImza182" Type="image" '
                        'Target="../media/imzaUretim182.png"/></Relationships>')
    assert len(re.findall(r'Id="rIdImza182"', rels)) == 1, "Id yinelenmis"


if __name__ == "__main__":
    test_kirli_sablon_temizlenir()
    test_temiz_sablon_bozulmaz()
    test_uretim_sonrasi_id_tek_kalir()
    print("imza testleri: TAMAM")
