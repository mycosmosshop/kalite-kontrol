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


# ── Tam balonlama: çizimdeki her ölçü ────────────────────────────────────
def _yazi_kutulari(im):
    """Bağlantılı bileşenle rakam boyutundaki yazıları bulur, sözcüğe birleştirir.
    Balonun YERİ buradan gelir; OCR'a bağlı değildir."""
    import cv2
    import numpy as np
    siyah = (im < 128).astype(np.uint8)
    n, _, ist, _ = cv2.connectedComponentsWithStats(siyah, 8)
    kar = []
    for i in range(1, n):
        x, y, g, h, alan = ist[i]
        if alan < 40:
            continue
        # Rakam BOYUNA olur (11-20 geniş × 22-30 yüksek). Ölçü çizgisinin ok
        # ucu ENİNE (29×20) ve ölçü sanılıp balonlanıyordu — en/boy ile elenir.
        if 18 <= h <= 60 and 6 <= g <= 60 and h > g * 1.05:
            kar.append((x, y, g, h, "y"))          # yatay yazı
        elif 18 <= g <= 60 and 6 <= h <= 60 and g > h * 1.05:
            kar.append((x, y, g, h, "d"))          # 90° döndürülmüş yazı

    def birlestir(kutu, yon):
        # Dikey yazida once SUTUN BANDI, sonra y: yalniz x'e gore siralamak
        # "485" gibi dikey sayilari boluyor ve her rakama ayri balon dusuyordu
        kutu = sorted(kutu, key=lambda k: (k[1], k[0]) if yon == "y"
                      else (k[0] // 24, k[1]))
        grup = []
        for x, y, g, h, _ in kutu:
            for gr in grup:
                # Bosluk esigi karakter yuksekligine gore: sabit 22 px'te
                # "188" gibi sayilar parcalanip birden fazla balon aliyordu
                bosluk = max(24, int(0.75 * (h if yon == "y" else g)))
                if yon == "y":
                    yakin = abs(y - gr["y"]) < 16 and -6 <= x - (gr["x"] + gr["g"]) < bosluk
                else:
                    yakin = abs(x - gr["x"]) < 16 and -6 <= y - (gr["y"] + gr["h"]) < bosluk
                if yakin:
                    gr["g"] = max(gr["x"] + gr["g"], x + g) - min(gr["x"], x)
                    gr["h"] = max(gr["y"] + gr["h"], y + h) - min(gr["y"], y)
                    gr["x"] = min(gr["x"], x)
                    gr["y"] = min(gr["y"], y)
                    break
            else:
                grup.append({"x": x, "y": y, "g": g, "h": h, "yon": yon})
        return grup

    return birlestir([k for k in kar if k[4] == "y"], "y") + \
           birlestir([k for k in kar if k[4] == "d"], "d")


def _olcu_disi(s, W, H, capa):
    """Çerçeve cetveli, antet, tablo ve 'Pos.' etiketleri ölçü değildir."""
    x, y = s["x"], s["y"]
    # Kenar cetveli dar bir bant; pay genis tutulunca cizimin sol kenarindaki
    # olculer (or. "255") de eleniyordu.
    if x < W * 0.021 or x > W * 0.978 or y < H * 0.022 or y > H * 0.972:
        return True
    if x > W * 0.655 and y > H * 0.735:
        return True
    if x > W * 0.825 and H * 0.49 < y < H * 0.78:
        return True
    # Etiket cevresindeki notlar ("x2", "©", "Scale: 1:5") olcu degildir;
    # dikey pencere dardi ve etiketin ALTINDAKI notlar balonlaniyordu.
    return any(abs(x - cx) < 420 and -80 < (y - cy) < 150 for cx, cy in capa)


def _yakinlari_birlestir(kutular, esik=26):
    """Ayni olcunun parcalanmis kutularini birlestirir.
    Ornek: "714" bazen "7" + "14" olarak iki kutu cikiyor ve ayni sayiya
    IKI BALON dusuyordu (kullanicinin gordugu "cift daire")."""
    kalan = sorted(kutular, key=lambda s: (s["yon"], s["y"], s["x"]))
    sonuc = []
    for s in kalan:
        for g in sonuc:
            if g["yon"] != s["yon"]:
                continue
            # kutular ust uste ya da okuma yonunde bitisikse ayni olcudur
            ax, ay = g["x"], g["y"]
            bx, by = s["x"], s["y"]
            # Yalniz AYNI sayinin parcalari birlesir: ayri olculeri
            # yutmamak icin esik dar tutulur (rakam araligi ~10-20 px).
            # Yatayda rakam araligi daha genis olabiliyor ("714" -> "7"+"14");
            # ama birlesmis kutu 6 haneden genis olmasin ki ayri olculer
            # yutulmasin.
            if g["yon"] == "y":
                yeni_g = max(ax + g["g"], bx + s["g"]) - min(ax, bx)
                yakin = (abs(ay - by) < 18 and -esik <= (bx - (ax + g["g"])) < esik * 1.6
                         and yeni_g < 7 * max(18, g["h"] * 0.62))
            else:
                yeni_h = max(ay + g["h"], by + s["h"]) - min(ay, by)
                yakin = (abs(ax - bx) < 18 and -esik <= (by - (ay + g["h"])) < esik * 1.6
                         and yeni_h < 7 * max(18, g["g"] * 0.62))
            if yakin:
                g["g"] = max(ax + g["g"], bx + s["g"]) - min(ax, bx)
                g["h"] = max(ay + g["h"], by + s["h"]) - min(ay, by)
                g["x"], g["y"] = min(ax, bx), min(ay, by)
                break
        else:
            sonuc.append(dict(s))
    # YON BAGIMSIZ eleme: ayni sayinin bir parcasi bazen "dikey yazi" diye
    # ayri kutu oluyor ve yan yana IKI balon cikiyordu. Ust uste binen ya da
    # cok yakin kutulardan BUYUK olan kalir.
    sonuc.sort(key=lambda z: -(z["g"] * z["h"]))
    kalanlar = []
    for s in sonuc:
        mx, my = s["x"] + s["g"] / 2, s["y"] + s["h"] / 2
        cakisir = False
        for g in kalanlar:
            gx, gy = g["x"] + g["g"] / 2, g["y"] + g["h"] / 2
            if abs(mx - gx) < 46 and abs(my - gy) < 34:
                cakisir = True
                break
            # kutu tamamen digerinin icindeyse de ayni olcudur
            if (g["x"] - 6 <= s["x"] and g["y"] - 6 <= s["y"]
                    and s["x"] + s["g"] <= g["x"] + g["g"] + 6
                    and s["y"] + s["h"] <= g["y"] + g["h"] + 6):
                cakisir = True
                break
        if not cakisir:
            kalanlar.append(s)
    return kalanlar


def _kutu_oku(im, s):
    """Küçük kırpma üzerinden çoklu geçiş okuma (ölçek × psm × yön oylaması)."""
    import pytesseract
    from PIL import Image
    pytesseract.pytesseract.tesseract_cmd = TESSERACT
    p = 10
    kirp = im[max(0, s["y"] - p):s["y"] + s["h"] + p, max(0, s["x"] - p):s["x"] + s["g"] + p]
    if kirp.size == 0:
        return None
    ham = Image.fromarray(kirp)
    oy = {}
    # Erken cikis: ilk gecis net bir sonuc verirse digerleri denenmez
    # (140 kutu x 9 gecis ~2000 OCR cagrisi cok yavas).
    for aci in ([-90, 90] if s["yon"] == "d" else [0]):
        b0 = ham.rotate(aci, expand=True) if aci else ham
        for kat in (6, 4, 8):
            if oy and max(oy.values()) >= 2:
                break
            b = b0.resize((b0.width * kat, b0.height * kat), Image.LANCZOS)
            for psm in ("7", "8", "13"):
                try:
                    t = pytesseract.image_to_string(
                        b, config="--psm " + psm +
                        " -c tessedit_char_whitelist=0123456789.,").strip()
                except Exception:
                    continue
                t = t.replace(",", ".").strip(" .")
                if re.fullmatch(r"\d{1,4}(\.\d{1,2})?", t or ""):
                    oy[t] = oy.get(t, 0) + 1
    if not oy:
        return None
    t = max(oy, key=oy.get)
    # GENISLIK TUTARLILIGI: kutu 3 hane genisligindeyse okuma da 3 haneli
    # olmali. "714" kutusundan "7" okunmasi boyle elenir; yanlis deger yerine
    # bos birakmak PPAP kaydinda daha dogru.
    uzun = s["g"] if s["yon"] == "y" else s["h"]
    hane = len(t.replace(".", ""))
    beklenen = max(1, round(uzun / max(12.0, s["h"] if s["yon"] == "y" else s["g"]) * 1.55))
    return t if abs(hane - beklenen) <= 1 else None


def _karakterler(im, s, etiket, ist, n):
    """Kutunun içindeki tek tek karakterler, okuma sırasına göre."""
    x0, y0, x1, y1 = s["x"], s["y"], s["x"] + s["g"], s["y"] + s["h"]
    liste = []
    for i in range(1, n):
        x, y, g, h, alan = ist[i]
        if alan < 40:
            continue
        if x >= x0 - 2 and y >= y0 - 2 and x + g <= x1 + 2 and y + h <= y1 + 2:
            liste.append((x, y, g, h, i))
    # yatay: soldan sağa · dikey (90° dönük): yukarıdan aşağı
    return sorted(liste, key=lambda c: c[0] if s["yon"] == "y" else c[1])


def _normal(etiket, c, boyut=24):
    import cv2
    import numpy as np
    x, y, g, h, i = c
    kes = (etiket[y:y + h, x:x + g] == i).astype(np.uint8) * 255
    return cv2.resize(kes, (boyut, boyut), interpolation=cv2.INTER_AREA).astype(np.float32)


def rakam_modeli(im, kutular, etiket, ist, n):
    """Rakam şablonlarını ÇİZİMİN KENDİSİNDEN öğrenir.
    OCR'ın güvenle okuduğu kutular tohum olur; çizimde tek font/boyut
    olduğu için şablon eşleştirme OCR'dan belirgin biçimde daha iyi okur."""
    import cv2
    import numpy as np
    tohum = {}
    for s in kutular:
        t = _kutu_oku(im, s)
        if not t or "." in t:
            continue
        kar = _karakterler(im, s, etiket, ist, n)
        if len(kar) != len(t):
            continue
        for c, d in zip(kar, t):
            a = _normal(etiket, c)
            if s["yon"] == "d":
                a = cv2.rotate(a, cv2.ROTATE_90_CLOCKWISE)
            tohum.setdefault(d, []).append(a)
    return {d: np.mean(v, axis=0) for d, v in tohum.items() if len(v) >= 2}


def _sablonla_oku(model, etiket, s, kar):
    """Karakterleri öğrenilmiş rakam şablonlarıyla okur."""
    import cv2
    import numpy as np
    if not model or not kar:
        return None
    hane, guven = [], []
    for c in kar:
        a = _normal(etiket, c)
        if s["yon"] == "d":
            a = cv2.rotate(a, cv2.ROTATE_90_CLOCKWISE)
        en, iyi = None, -2.0
        for d, m in model.items():
            p = float(np.corrcoef(a.ravel(), m.ravel())[0, 1])
            if p > iyi:
                iyi, en = p, d
        hane.append(en or "?")
        guven.append(iyi)
    t = "".join(hane)
    return t if ("?" not in t and guven and min(guven) > 0.55) else None


def tum_olculer(im, capa, plan_degerleri=()):
    """Çizimdeki tüm ölçü kutuları: [(deger|None, x, y, g, h, kaynak)].
    kaynak: 'plan' (kontrol planıyla doğrulandı) · 'okundu' · None (okunamadı)"""
    import cv2
    import numpy as np
    H, W = im.shape
    kutu = _yakinlari_birlestir(
        [s for s in _yazi_kutulari(im) if not _olcu_disi(s, W, H, capa)])
    plan = {("%g" % float(d)) for d in plan_degerleri}
    siyah = (im < 128).astype(np.uint8)
    n_bil, etiket, ist, _ = cv2.connectedComponentsWithStats(siyah, 8)
    model = rakam_modeli(im, kutu, etiket, ist, n_bil)
    sonuc = []
    for s in kutu:
        kar = _karakterler(im, s, etiket, ist, n_bil)
        t = _sablonla_oku(model, etiket, s, kar) or _kutu_oku(im, s)
        kaynak = None
        if t is not None:
            kaynak = "plan" if ("%g" % float(t)) in plan else "okundu"
        sonuc.append((t, s["x"], s["y"], s["g"], s["h"], kaynak, s["yon"]))
    return sonuc


def _en_yakin_pos(x, y, capa_no):
    """Ölçüyü ait olduğu pozisyona bağlar (en yakın 'Pos.' etiketi)."""
    if not capa_no:
        return None
    return min(capa_no, key=lambda c: (c[1] - x) ** 2 + (c[2] - y) ** 2)[0]


def balonla(tiff_yolu, hedef_png, atamalar, baslik=""):
    """Balonları çizip kaydeder. Okunamayan balon SARI çizilir (gözden geçir)."""
    from PIL import Image, ImageDraw, ImageFont
    renk = Image.open(tiff_yolu).convert("RGB")
    ciz = ImageDraw.Draw(renk)
    try:
        yazi = ImageFont.truetype("arialbd.ttf", 40)
        kucuk_no = ImageFont.truetype("arialbd.ttf", 26)
        kucuk = ImageFont.truetype("arial.ttf", 30)
    except OSError:
        yazi = kucuk = kucuk_no = ImageFont.load_default()
    # Tek renk duzeni: okunan KIRMIZI, okunamayan SARI. Once "plan/okundu"
    # ayrimi icin iki renk vardi, cizimde karisik gorunuyordu; o ayrim
    # olcusel raporun "Not" sutununda zaten yaziyor.
    RENK = {"plan": (200, 0, 0), "okundu": (200, 0, 0), "sıradan": (200, 0, 0)}
    for no, x, y, kaynak in atamalar:
        cx, cy = x, y
        boya = RENK.get(kaynak, (215, 150, 0))       # bilinmiyorsa sarı
        e = str(no) if no is not None else "?"
        r = 34 if len(e) > 2 else 40
        ciz.ellipse([cx - r, cy - r, cx + r, cy + r], outline=boya, width=6)
        f = kucuk_no if len(e) > 3 else yazi
        k = ciz.textbbox((0, 0), e, font=f)
        ciz.text((cx - (k[2] - k[0]) / 2, cy - (k[3] - k[1]) / 2 - 6), e, fill=boya, font=f)
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
        # Sabit ad kullanilirsa onceki calismanin gecici dosyasi silinip
        # yenisi acilamadan kullanilabiliyor; her cagriya ozel ad verilir.
        g = os.path.join(tempfile.gettempdir(),
                         "apqp_cizim_%d%s" % (abs(hash(yol)) % 10 ** 8, uz))
        if not os.path.exists(g):
            shutil.copy2(yol, g)
        return g, True
    except OSError:
        return yol, False


def uret(kod, tiff_yolu, klasor, kp_satirlari, sablon_kutusu=None, tam=True):
    """Ürün için balonlu teknik resmi üretir.
    tam=True → çizimdeki HER ölçü balonlanır (PPAP 2.2.1 tam kapsam).
    Dönüş: (balon sayısı, rapor metni, satırlar)
      satırlar: [{"no","deger","kaynak","pos","x","y"}] — ölçüsel rapor için.
    """
    import cv2
    tiff_yolu, _ = _yerele_al(tiff_yolu)
    if tiff_yolu.lower().endswith(".pdf"):
        tiff_yolu = _pdf_goruntu(tiff_yolu)
    im = cv2.imread(tiff_yolu, cv2.IMREAD_GRAYSCALE)
    if im is None or not os.path.exists(tiff_yolu):
        return 0, "çizim okunamadı: " + tiff_yolu, []
    pos = _pos_kumesi(kp_satirlari, kod)

    if sablon_kutusu:
        y0, y1, x0, x1 = sablon_kutusu
        sablon = im[y0:y1, x0:x1]
    else:
        sablon = _sablon_ogren(im)
    if sablon is None:
        return 0, "'Pos.' etiketi bulunamadı", []

    capa = _capalar(im, sablon)
    if not capa:
        return 0, "pozisyon etiketi bulunamadı", []
    capa_no = numaralari_ata(im, capa, set(pos)) if pos else _serbest_ata(im, capa)

    if not tam:
        atama = [(a[0], a[1], a[2], a[3]) for a in capa_no]
        satirlar = []
    else:
        plan_deger = [d[0] for k in pos.values() for d in k]
        olcu = tum_olculer(im, capa, plan_deger)
        # Her ölçü en yakın pozisyona bağlanır, o grupta okuma sırasıyla numaralanır
        gruplar = {}
        for deger, x, y, g, h, kaynak, yon in olcu:
            gruplar.setdefault(_en_yakin_pos(x, y, capa_no), []).append(
                {"deger": deger, "x": x, "y": y, "g": g, "h": h,
                 "kaynak": kaynak, "yon": yon})
        atama, satirlar = [], []
        for pno in sorted(gruplar, key=lambda z: (z is None, z)):
            liste = sorted(gruplar[pno], key=lambda o: (o["y"] // 60, o["x"]))
            for i, o in enumerate(liste):
                etiket = "%s.%d" % (pno, i + 1) if pno is not None else "?.%d" % (i + 1)
                # Balon yazinin USTUNE binmesin: yatay yazida soluna,
                # dikey (90 donuk) yazida ustune konur
                if o.get("yon") == "d":
                    bx, by = o["x"] + o["g"] // 2, o["y"] - 78
                else:
                    bx, by = o["x"] - 78, o["y"] + o["h"] // 2
                atama.append((etiket, bx, by, o["kaynak"]))
                satirlar.append({"no": etiket, "deger": o["deger"], "kaynak": o["kaynak"],
                                 "pos": pno, "x": o["x"], "y": o["y"]})

    ad = "Numaralandırılmış Teknik Resim %s" % kod
    png = os.path.join(klasor, ad + ".png")
    balonla(tiff_yolu, png, atama,
            "%s — tüm ölçüler balonlu · sarı balon: çizimden okunamadı, "
            "değeri ölçüsel rapora elle girilecek" % kod)
    pdf_yaz(png, os.path.join(klasor, ad + ".pdf"))

    dogru = sum(1 for a in atama if a[3] == "plan")
    okundu = sum(1 for a in atama if a[3] == "okundu")
    kalan = len(atama) - dogru - okundu
    rapor = ("%d balon — %d kontrol planıyla doğrulandı, %d okundu, %d okunamadı"
             % (len(atama), dogru, okundu, kalan)) if tam else (
        "%d pozisyon balonu" % len(atama))
    return len(atama), rapor, satirlar


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
    n, rapor, satir = uret(kod, resim, os.path.join(ag.DRIVE, kod), ag.kp_satirlari)
    print("%s → %s" % (kod, rapor))
