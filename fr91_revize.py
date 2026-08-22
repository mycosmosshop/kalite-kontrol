# -*- coding: utf-8 -*-
"""FR91 APQP-Takip Formunu AIAG APQP 3rd Edition (Mart 2024) listesine göre
revize eder.

  python fr91_revize.py [kaynak FR91.xlsx] [hedef.xlsx]

Şablonda logo şekli, koşullu biçimlendirme ve veri doğrulama var; openpyxl
bunları kaybediyor. Bu yüzden satırlar ZIP DÜZEYİNDE ekleniyor: sayfa XML'inde
ekleme noktasının altındaki her şey (satır numaraları, hücre referansları,
birleşimler, koşullu biçim ve doğrulama aralıkları, çizim çapaları) kaydırılıyor,
geri kalan her parça bit bit korunuyor.

Kaynak dosyaya DOKUNULMAZ; yeni bir şablon dosyası üretilir.
"""
import sys, os, re, io, zipfile

# Eklenecek maddeler: apqp_adimlari_tazele.py ile aynı kaynak
from apqp_adimlari_tazele import EK_ADIMLAR, EK_BOLUM, cikar

VARSAYILAN = r"G:\Drive'ım\APQP\205.0.214-C\FR91 APQP-Takip Formu 36.72010-6345.xlsx"
SAYFA = "xl/worksheets/sheet1.xml"

# FR91 sütun düzeni (bkz. apqp_adimlari_tazele.py)
SUTUN = {"no": "B", "ad": "E", "aiag": "T", "sorumluluk": "X", "prosedur": "Z", "form": "AA"}


def sutun_no(h):
    n = 0
    for c in h:
        n = n * 26 + (ord(c) - 64)
    return n


def _kaydir_ref(ref, esik, adet):
    """A12 -> A18 gibi (satır eşikten büyükse)."""
    m = re.match(r"([A-Z]+)(\d+)$", ref)
    if not m:
        return ref
    r = int(m.group(2))
    return "%s%d" % (m.group(1), r + adet) if r >= esik else ref


def _kaydir_aralik(aralik, esik, adet):
    return " ".join(":".join(_kaydir_ref(x, esik, adet) for x in p.split(":"))
                    for p in aralik.split())


def satir_kaydir(xml, esik, adet):
    """Eşik satırı ve altındaki her şeyi `adet` kadar aşağı iter."""
    # <row r="N"> ve içindeki <c r="XN">
    def row_repl(m):
        r = int(m.group(2))
        if r < esik:
            return m.group(0)
        govde = re.sub(r'(<c r=")([A-Z]+)(\d+)(")',
                       lambda c: '%s%s%d%s' % (c.group(1), c.group(2), int(c.group(3)) + adet, c.group(4)),
                       m.group(3))
        return '%s%d%s' % (m.group(1), r + adet, govde)

    xml = re.sub(r'(<row r=")(\d+)(".*?</row>)', row_repl, xml, flags=re.S)
    # spans niteliği satır bazlı değil, dokunulmuyor.
    # Birleşimler, koşullu biçim, doğrulama, otomatik filtre aralıkları
    for etiket in ("mergeCell ref", "conditionalFormatting sqref", "dataValidation .*?sqref",
                   "autoFilter ref", "dimension ref"):
        pass
    xml = re.sub(r'(<mergeCell ref=")([^"]+)(")',
                 lambda m: m.group(1) + _kaydir_aralik(m.group(2), esik, adet) + m.group(3), xml)
    xml = re.sub(r'(<conditionalFormatting sqref=")([^"]+)(")',
                 lambda m: m.group(1) + _kaydir_aralik(m.group(2), esik, adet) + m.group(3), xml)
    xml = re.sub(r'(sqref=")([^"]+)(")',
                 lambda m: m.group(1) + _kaydir_aralik(m.group(2), esik, adet) + m.group(3), xml)
    xml = re.sub(r'(<dimension ref=")([^"]+)(")',
                 lambda m: m.group(1) + _kaydir_aralik(m.group(2), esik, adet) + m.group(3), xml)
    return xml


def cizim_kaydir(cizim, esik, adet):
    """Çizim çapaları 0 tabanlı satır kullanır."""
    def repl(m):
        r = int(m.group(1))
        return "<xdr:row>%d</xdr:row>" % (r + adet if r >= esik - 1 else r)
    return re.sub(r"<xdr:row>(\d+)</xdr:row>", repl, cizim)


def satir_kopyala(xml, kaynak_satir, hedef_satir, degerler):
    """Kaynak satırın biçimini kopyalayıp hedef satırı üretir."""
    m = re.search(r'<row r="%d"[^>]*>.*?</row>' % kaynak_satir, xml, re.S)
    if not m:
        return None
    blok = m.group(0)
    # Satır numarasını değiştir
    yeni = re.sub(r'(<row r=")\d+(")', r'\g<1>%d\g<2>' % hedef_satir, blok)
    yeni = re.sub(r'(<c r="[A-Z]+)\d+(")', r'\g<1>%d\g<2>' % hedef_satir, yeni)
    # Tüm hücreleri boşalt (biçim kalsın). Kendi kendini kapatan hücreler
    # (<c .../>) zaten boş; onları da aynı kalıpla ele almak gerekiyor, yoksa
    # ".*?</c>" bir sonraki hücreye taşıp XML'i bozuyor.
    def bosalt(c):
        # DIKKAT: adlandirilmis grup da 1. gruptur; oznitelikler 2. gruptadir
        oz = re.sub(r'\st="[^"]*"', "", c.group(2))
        return '<c r="%s"%s/>' % (c.group("ref"), oz)

    yeni = re.sub(r'<c r="(?P<ref>[A-Z]+\d+)"([^>]*?)(?:/>|>.*?</c>)',
                  bosalt, yeni, flags=re.S)
    # İstenen değerleri yaz
    for harf, deger in degerler.items():
        ref = "%s%d" % (harf, hedef_satir)
        icerik = '<is><t xml:space="preserve">%s</t></is>' % (
            str(deger).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
        km = re.search(r'<c r="%s"([^>/]*)(/>|>.*?</c>)' % ref, yeni, re.S)
        if km:
            oz = re.sub(r'\st="[^"]*"', "", km.group(1))
            yeni = yeni[:km.start()] + '<c r="%s"%s t="inlineStr">%s</c>' % (ref, oz, icerik) + yeni[km.end():]
    return yeni


def satir_bul(xml, bolum_no, adim_sayisi):
    """Bölümün SON adım satırını bulur (yeni adımlar bunun altına eklenir)."""
    son = None
    for m in re.finditer(r'<row r="(\d+)"[^>]*>(.*?)</row>', xml, re.S):
        r, govde = int(m.group(1)), m.group(2)
        bm = re.search(r'<c r="B%d"[^>]*>(?:<is><t[^>]*>|<v>)([^<]*)' % r, govde)
        if not bm:
            continue
        deger = bm.group(1).strip()
        if re.match(r"^%s(\.\d+)?$" % re.escape(bolum_no), deger):
            son = r
    return son


def main():
    kaynak = sys.argv[1] if len(sys.argv) > 1 else VARSAYILAN
    hedef = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        os.path.dirname(kaynak) or ".",
        "FR91 APQP-Takip Formu (AIAG 3rd Ed) ŞABLON.xlsx")

    zin = zipfile.ZipFile(kaynak)
    xml = zin.read(SAYFA).decode("utf-8")
    cizim_yolu = next((n for n in zin.namelist() if "drawings/drawing" in n and n.endswith(".xml")), None)
    cizim = zin.read(cizim_yolu).decode("utf-8") if cizim_yolu else None

    # Şablondaki mevcut bölümler (biçim kopyalanacak örnek satırlar için)
    bolumler = cikar(kaynak)
    print("%s\n   şablonda %d bölüm / %d adım"
          % (os.path.basename(kaynak), len(bolumler), sum(len(b["adimlar"]) for b in bolumler)))

    eklenen = 0
    # Bölümleri SONDAN başa işle: üstteki eklemeler alttakinin satır no'sunu kaydırmasın
    for bno in sorted(EK_ADIMLAR, key=lambda x: int(x), reverse=True):
        maddeler = EK_ADIMLAR[bno]
        b = next((x for x in bolumler if x["no"] == bno), None)
        if b:
            son = satir_bul(xml, bno, len(b["adimlar"]))
            baslangic_no = len(b["adimlar"]) + 1
        else:
            # Yeni bölüm: tablonun en altına, başlık satırıyla birlikte
            son = max(int(m.group(1)) for m in re.finditer(r'<row r="(\d+)"', xml))
            baslangic_no = 1
        if not son:
            print("   ! bölüm %s bulunamadı, atlandı" % bno)
            continue

        ornek = son                       # biçim kaynağı: bölümün son adım satırı
        adet = len(maddeler) + (0 if b else 1)
        xml = satir_kaydir(xml, son + 1, adet)
        if cizim:
            cizim = cizim_kaydir(cizim, son + 1, adet)

        yeni_satirlar = []
        r = son + 1
        if not b:                          # yeni bölüm başlığı
            blok = satir_kopyala(xml, ornek, r, {"B": bno, "E": EK_BOLUM.get(bno, "Ek")})
            if blok:
                yeni_satirlar.append(blok)
            r += 1
        for i, (ad, aiag, sorumluluk, prosedur, form) in enumerate(maddeler):
            deger = {"B": "%s.%d" % (bno, baslangic_no + i), "E": ad, "T": aiag,
                     "X": sorumluluk, "Z": prosedur, "AA": form}
            blok = satir_kopyala(xml, ornek, r, {k: v for k, v in deger.items() if v})
            if blok:
                yeni_satirlar.append(blok)
            r += 1

        # Örnek satırın hemen ardına yerleştir
        m = re.search(r'<row r="%d"[^>]*>.*?</row>' % ornek, xml, re.S)
        xml = xml[:m.end()] + "".join(yeni_satirlar) + xml[m.end():]
        eklenen += len(maddeler)
        print("   bölüm %s: +%d adım (satır %d altına)" % (bno, len(maddeler), ornek))

    zout = zipfile.ZipFile(hedef, "w", zipfile.ZIP_DEFLATED)
    for e in zin.infolist():
        if e.filename == SAYFA:
            zout.writestr(e, xml.encode("utf-8"))
        elif cizim and e.filename == cizim_yolu:
            zout.writestr(e, cizim.encode("utf-8"))
        else:
            zout.writestr(e, zin.read(e.filename))
    zout.close()
    zin.close()
    print("   → %s  (+%d adım)" % (os.path.basename(hedef), eklenen))


if __name__ == "__main__":
    main()
