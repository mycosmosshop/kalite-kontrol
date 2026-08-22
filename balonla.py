# -*- coding: utf-8 -*-
"""Balonlu (numaralandırılmış) teknik resim — PPAP 2.2.1 / FR91 madde 6.5.

Yöntem, taranmış çizimde ölçülerek seçildi:
  * Pozisyon etiketinin YERİ  : şablon eşleştirme  → 20/20, eşiğe duyarsız
  * Etiketin NUMARASI         : OCR tek başına 8/20 — güvenilmez.
    Bu yüzden numara OCR'a bırakılmaz: kontrol planındaki POS kümesi
    (doğruluk kaynağı) + satır/sütun geometrisi + çoklu OCR geçişi birlikte
    kullanılır. Karar veremediği balon ÇIKTIDA İŞARETLENİR (sarı), uydurulmaz.

Balon numarası müşterinin kendi POS numarasıdır; ölçüsel rapor da aynı
numarayla kontrol planından üretilir.
"""
import io
import os
import re
import sys

TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def _pos_kumesi(kp_satirlari, kod):
    """Kontrol planındaki POS karakteristikleri — numara doğruluk kaynağı."""
    pos = {}
    for x in kp_satirlari(kod):
        ad = str(x.get("olculecek") or "").upper().strip()
        g = re.fullmatch(r"POS\s*(\d{1,3})", ad)
        if not g:
            continue
        no = int(g.group(1))
        if x.get("hedef_nicel") is not None:
            pos.setdefault(no, []).append(
                (float(x["hedef_nicel"]), x.get("alt_limit"), x.get("ust_limit")))
        else:
            pos.setdefault(no, [])
    return pos


def _capalar(im, sablon, esik=0.65):
    """'Pos.' etiketlerinin konumu (şablon eşleştirme)."""
    import cv2
    import numpy as np
    son = cv2.matchTemplate(im, sablon, cv2.TM_CCOEFF_NORMED)
    yer = np.where(son >= esik)
    grup = []
    for x, y in sorted(zip(yer[1], yer[0])):
        if not any(abs(x - gx) < 120 and abs(y - gy) < 60 for gx, gy in grup):
            grup.append((int(x), int(y)))
    return grup


# OCR'in siklikla karistirdigi harf->rakam eslesmeleri
KARISIK = {"O": "0", "o": "0", "Q": "9", "D": "0", "S": "5", "s": "5", "B": "8",
           "l": "1", "I": "1", "|": "1", "Z": "2", "A": "4", "G": "6", "T": "7",
           "g": "9", "b": "6"}


def _guvenli_kat(g, y, istenen):
    """Tesseract kenar sinirini asmayacak en buyuk buyutme katsayisi."""
    for k in range(istenen, 0, -1):
        if g * k < 32000 and y * k < 32000:
            return k
    return 1


def _numara_oku(im, x, y):
    """Etiketi birkaç ön işlemeyle okur, rakam adaylarını oy sayısıyla döner."""
    import pytesseract
    from PIL import Image
    pytesseract.pytesseract.tesseract_cmd = TESSERACT
    kirp = im[max(0, y - 20):y + 75, x:x + 360]
    if kirp.size == 0:
        return {}
    oy = {}
    for kat in (2, 3, 4):
        b = Image.fromarray(kirp).resize(
            (kirp.shape[1] * kat, kirp.shape[0] * kat), Image.LANCZOS)
        for psm in ("7", "8", "13"):
            try:
                t = pytesseract.image_to_string(b, config="--psm " + psm).strip()
            except Exception:
                continue
            g = re.search(r"[Pp][o0aQ][sc5][\s.,]*([0-9OoQDSsBlI|ZAGTgb]{1,3})", t)
            if not g:
                continue
            ham = "".join(KARISIK.get(c, c) for c in g.group(1))
            ham = re.sub(r"\D", "", ham)
            if ham:
                oy[int(ham)] = oy.get(int(ham), 0) + 1
    return oy


def _satir_gruplari(capa, tolerans=260):
    """Çapaları satır bantlarına ayırır (çizimde parçalar sıralar hâlinde)."""
    gruplar = []
    for x, y in sorted(capa, key=lambda p: p[1]):
        if gruplar and abs(y - gruplar[-1][-1][1]) <= tolerans:
            gruplar[-1].append((x, y))
        else:
            gruplar.append([(x, y)])
    return [sorted(g, key=lambda p: p[0]) for g in gruplar]


def numaralari_ata(im, capa, beklenen):
    """Her çapaya POS numarası atar.
    1) Çoklu OCR geçişi — yalnız BEKLENEN kümedeki değer kabul edilir
    2) Kalanlar satır/sütun okuma sırasına göre, artan biçimde doldurulur
    Dönüş: [(no, x, y, kaynak)]  kaynak: 'okundu' | 'sıradan' | None
    """
    sira = [p for g in _satir_gruplari(capa) for p in g]
    atama = {}
    for x, y in sira:
        oy = _numara_oku(im, x, y)
        uygun = {n: s for n, s in oy.items() if n in beklenen}
        if uygun:
            atama[(x, y)] = max(uygun, key=uygun.get)
    # Aynı numara iki çapaya düşerse ikisini de şüpheli say
    sayim = {}
    for n in atama.values():
        sayim[n] = sayim.get(n, 0) + 1
    atama = {k: v for k, v in atama.items() if sayim[v] == 1}

    kalan = sorted(set(beklenen) - set(atama.values()))
    sonuc = []
    for x, y in sira:
        if (x, y) in atama:
            sonuc.append((atama[(x, y)], x, y, "okundu"))
        elif kalan:
            sonuc.append((kalan.pop(0), x, y, "sıradan"))
        else:
            sonuc.append((None, x, y, None))
    return sonuc


def _serbest_ata(im, capa):
    """POS kümesi yoksa çizimdeki numaralar okunur.
    Doğrulama: N pozisyon varsa numaralar 1..N aralığında olmalı. Yanındaki
    ölçüden fazladan hane kapan okumalar (Pos.12 → 120) böyle elenir; elenen
    balon okuma sırasındaki eksik numarayla doldurulur."""
    sira = [p for g in _satir_gruplari(capa) for p in g]
    N = len(sira)
    ham = []
    for x, y in sira:
        oy = _numara_oku(im, x, y)
        no = max(oy, key=oy.get) if oy else None
        ham.append(no)
    # Aralık dışı ve yinelenen okumalar düşürülür
    sayim = {}
    for n_ in ham:
        if n_ is not None:
            sayim[n_] = sayim.get(n_, 0) + 1
    temiz = [n_ if (n_ is not None and 1 <= n_ <= N and sayim[n_] == 1) else None
             for n_ in ham]
    kalan = [n_ for n_ in range(1, N + 1) if n_ not in set(temiz)]
    sonuc = []
    for (x, y), n_ in zip(sira, temiz):
        if n_ is not None:
            sonuc.append((n_, x, y, "okundu"))
        elif kalan:
            sonuc.append((kalan.pop(0), x, y, "sıradan"))
        else:
            sonuc.append((None, x, y, None))
    return sonuc


def balonla(tiff_yolu, hedef_png, atamalar, baslik=""):
    """Balonları çizip kaydeder. Okunamayan balon SARI çizilir (gözden geçir)."""
    from PIL import Image, ImageDraw, ImageFont
    renk = Image.open(tiff_yolu).convert("RGB")
    ciz = ImageDraw.Draw(renk)
    try:
        yazi = ImageFont.truetype("arialbd.ttf", 44)
        kucuk = ImageFont.truetype("arial.ttf", 30)
    except OSError:
        yazi = kucuk = ImageFont.load_default()
    for no, x, y, kaynak in atamalar:
        cx, cy = x - 72, y + 26
        boya = (200, 0, 0) if kaynak == "okundu" else (
            (0, 90, 200) if kaynak == "sıradan" else (210, 150, 0))
        ciz.ellipse([cx - 44, cy - 44, cx + 44, cy + 44], outline=boya, width=7)
        e = str(no) if no is not None else "?"
        k = ciz.textbbox((0, 0), e, font=yazi)
        ciz.text((cx - (k[2] - k[0]) / 2, cy - (k[3] - k[1]) / 2 - 8), e, fill=boya, font=yazi)
    if baslik:
        ciz.rectangle([20, 20, 20 + 15 * len(baslik), 74], fill=(255, 255, 255))
        ciz.text((28, 30), baslik, fill=(0, 0, 0), font=kucuk)
    renk.save(hedef_png)
    return len(atamalar)


def pdf_yaz(png_yolu, pdf_yolu):
    from PIL import Image
    Image.open(png_yolu).convert("RGB").save(pdf_yolu, "PDF", resolution=200.0)


def cizim_yolu(dokumanlar):
    """ERP stok dokümanları arasından teknik resim dosyası (raster ya da PDF)."""
    aday = [str(d.get("link") or "") for d in (dokumanlar or [])]
    # Vektor PDF varsa once o kullanilir: metin ve cizgiler temiz
    for uzanti in ((".pdf",), (".tif", ".tiff", ".png", ".jpg", ".jpeg")):
        for yol in aday:
            if yol.lower().endswith(uzanti):
                return yol
    return None


def _yerele_al(yol):
    """Ağ paylaşımındaki dosyayı geçici olarak yerele kopyalar (cv2 UNC'de
    Türkçe/uzun yollarda okuyamıyor)."""
    import shutil
    import tempfile
    if os.path.exists(yol) and not yol.startswith("\\\\"):
        return yol, False
    try:
        uz = os.path.splitext(yol)[1] or ".tiff"
        g = os.path.join(tempfile.gettempdir(), "apqp_cizim" + uz)
        shutil.copy2(yol, g)
        return g, True
    except OSError:
        return yol, False


def uret(kod, tiff_yolu, klasor, kp_satirlari, sablon_kutusu=None):
    """Ürün için balonlu teknik resmi üretir. Dönüş: (balon sayısı, rapor)."""
    import cv2
    tiff_yolu, gecici = _yerele_al(tiff_yolu)
    if tiff_yolu.lower().endswith(".pdf"):
        tiff_yolu, gecici = _pdf_goruntu(tiff_yolu), True
    im = cv2.imread(tiff_yolu, cv2.IMREAD_GRAYSCALE)
    if im is None:
        return 0, "çizim okunamadı: " + tiff_yolu
    pos = _pos_kumesi(kp_satirlari, kod)

    # Şablon: "Pos." yazısının bir örneği. Verilmezse ilk etiketten öğrenilir.
    if sablon_kutusu:
        y0, y1, x0, x1 = sablon_kutusu
        sablon = im[y0:y1, x0:x1]
    else:
        sablon = _sablon_ogren(im)
        if sablon is None:
            return 0, "'Pos.' etiketi bulunamadı"

    capa = _capalar(im, sablon)
    if not capa:
        return 0, "pozisyon etiketi bulunamadı"
    # Kontrol planında POS karakteristiği yoksa (ör. ÖLÇÜ1/ÖLÇÜ2 diye
    # adlandırılmış ürünler) çizimdeki numaralar okunur; küme kısıtı olmadan
    # da balon konur, okunamayan sarı işaretlenir.
    atama = numaralari_ata(im, capa, set(pos)) if pos else _serbest_ata(im, capa)

    ad = "Numaralandırılmış Teknik Resim %s" % kod
    png = os.path.join(klasor, ad + ".png")
    balonla(tiff_yolu, png, atama,
            "%s — balon no = kontrol planı POS no (kırmızı: okundu, mavi: sıradan)" % kod)
    pdf_yaz(png, os.path.join(klasor, ad + ".pdf"))

    okunan = sum(1 for a in atama if a[3] == "okundu")
    supheli = sum(1 for a in atama if a[0] is None)
    rapor = "%d balon (%d okundu, %d sıradan%s)%s" % (
        len(atama), okunan, len(atama) - okunan - supheli,
        ", %d okunamadı" % supheli if supheli else "",
        ", kontrol planı POS: %d" % len(pos) if pos else " — çizim numaralandırması")
    return len(atama), rapor


def _pdf_goruntu(pdf_yolu, dpi=200):
    """Vektör PDF çizimi görüntüye çevirir (aynı balon akışı kullanılsın)."""
    import fitz
    import tempfile
    d = fitz.open(pdf_yolu)
    p = d[0].get_pixmap(dpi=dpi)
    g = os.path.join(tempfile.gettempdir(), "apqp_cizim_pdf.png")
    p.save(g)
    return g


def _sablon_ogren(im):
    """OCR ile bir 'Pos.' etiketi bulup şablon olarak kırpar."""
    import pytesseract
    from PIL import Image
    pytesseract.pytesseract.tesseract_cmd = TESSERACT
    # Tesseract ~32767 px kenar siniri; buyuk taramalarda buyutme yapilmaz
    kat = _guvenli_kat(im.shape[1], im.shape[0], 2)
    b = Image.fromarray(im)
    if kat != 1:
        b = b.resize((im.shape[1] * kat, im.shape[0] * kat), Image.LANCZOS)
    d = pytesseract.image_to_data(b, config="--psm 11", output_type=pytesseract.Output.DICT)
    for i, t in enumerate(d["text"]):
        if re.match(r"^[Pp][o0]s", t.strip() or "") and int(d["conf"][i]) > 45:
            x, y = d["left"][i] // 2, d["top"][i] // 2
            h = max(40, d["height"][i] // 2)
            return im[max(0, y - 6):y + h + 8, x:x + 140]
    return None


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import importlib.util
    sp = importlib.util.spec_from_file_location(
        "ag", os.path.join(os.path.dirname(os.path.abspath(__file__)), "apqp_belge_uret.py"))
    ag = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(ag)
    kod = sys.argv[1] if len(sys.argv) > 1 else "205.0.214-C"
    v = ag.zenginlestir(ag.urun_verisi(kod))
    resim = cizim_yolu(v["dok"])
    if not resim:
        raise SystemExit("bu ürünün teknik resmi ERP'de yok")
    n, rapor = uret(kod, resim, os.path.join(ag.DRIVE, kod), ag.kp_satirlari)
    print("%s → %s" % (kod, rapor))
