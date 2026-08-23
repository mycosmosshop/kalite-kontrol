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


def _plan_degerleri(kp_satirlari, kod):
    """Kontrol planındaki tüm ölçülebilir nominal değerler (POS'suz planlar
    için doğrulama kaynağı)."""
    deger = []
    for x in kp_satirlari(kod):
        alt, ust = x.get("alt_limit"), x.get("ust_limit")
        hedef = x.get("hedef_nicel")
        try:
            if hedef not in (None, ""):
                deger.append(float(hedef))
            elif alt is not None and ust is not None:
                deger.append((float(alt) + float(ust)) / 2)
        except (TypeError, ValueError):
            continue
    return deger


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
    # Cerceve cetveli (kenar harf/rakamlari) icin pay. Balon kutunun soluna
    # ciziliyor; kenar harfleri paya kil payi girmiyordu.
    if x < W * 0.032 or x > W * 0.978 or y < H * 0.022 or y > H * 0.972:
        return True
    if x > W * 0.655 and y > H * 0.735:
        return True
    if x > W * 0.825 and H * 0.49 < y < H * 0.78:
        return True
    # Etiket cevresindeki notlar ("x2", "©", "Scale: 1:5") olcu degildir;
    # dikey pencere dardi ve etiketin ALTINDAKI notlar balonlaniyordu.
    return any(abs(x - cx) < 420 and -80 < (y - cy) < 150 for cx, cy in capa)


def _cember_icinde(im, s):
    """Sayı ZATEN bir çemberin içinde mi? (çizimin kendi referans balonu)

    Teknik resimlerde detay/kesit referansları daire içinde numaralanır.
    Bunlara yeniden balon konmamalı — kullanıcının tespiti.
    """
    import numpy as np
    H, W = im.shape
    cx, cy = s["x"] + s["g"] / 2.0, s["y"] + s["h"] / 2.0
    R = max(s["g"], s["h"]) * 0.75
    if R < 6:
        return False
    aci = np.linspace(0, 2 * np.pi, 36, endpoint=False)
    isabet = 0
    for a in aci:
        for kat in (0.95, 1.15, 1.35):
            x = int(round(cx + np.cos(a) * R * kat))
            y = int(round(cy + np.sin(a) * R * kat))
            if 0 <= x < W and 0 <= y < H and im[y, x] < 128:
                isabet += 1
                break
    return isabet >= len(aci) * 0.8


def _olcu_cizgisi_var(im, s):
    """Kutunun yanında ÖLÇÜ ÇİZGİSİ var mı?

    Gerçek ölçü, kendisinden belirgin biçimde uzun bir ölçü çizgisine
    yaslanır. Antet yazısı, not cümlesi ve standart referansı ("VW 10500")
    böyle bir çizgiye yaslanmaz. Bu POZİTİF kanıt, eskiden kullandığım
    yoğunluk elemesinin yerini alır — o eleme ölçü yoğun bölgelerde gerçek
    ölçüleri de kesiyordu (kullanıcı: "birçok sayıya balon verilmemiş").
    """
    import numpy as np
    H, W = im.shape
    dikey = s.get("yon") == "d"
    # Okuma yönündeki uzunluk ve ona dik kalınlık
    uzun = s["h"] if dikey else s["g"]
    kalin = s["g"] if dikey else s["h"]
    if uzun < 4 or kalin < 4:
        return False
    gerek = max(int(uzun * 2.0), 40)
    a0 = int(max(0, (s["y"] if dikey else s["x"]) - uzun * 1.5))
    a1 = int(min(H if dikey else W, (s["y"] + s["h"] if dikey else s["x"] + s["g"])
                 + uzun * 1.5))
    if a1 - a0 < gerek:
        return False

    def tarama(b0, b1):
        b0, b1 = int(max(0, b0)), int(min(W if dikey else H, b1))
        if b1 <= b0:
            return False
        bant = (im[a0:a1, b0:b1] if dikey else im[b0:b1, a0:a1]) < 128
        # Her hat (dikey yazıda sütun) boyunca en uzun koyu diziyi bul
        for i in range(bant.shape[1] if dikey else bant.shape[0]):
            hat = bant[:, i] if dikey else bant[i]
            en, sayac = 0, 0
            for p in hat:
                sayac = sayac + 1 if p else 0
                if sayac > en:
                    en = sayac
            if en >= gerek:
                return True
        return False

    ust = (s["x"] if dikey else s["y"])
    alt = (s["x"] + s["g"] if dikey else s["y"] + s["h"])
    return (tarama(ust - kalin * 2.5, ust - kalin * 0.15)
            or tarama(alt + kalin * 0.15, alt + kalin * 2.5))


def _metin_satirinda(s, hepsi):
    """Kutu bir YAZI SATIRININ parçası mı? (aynı hizada, yakınında başka
    kutu var mı)

    Gerçek ölçü çizim alanında TEK BAŞINA durur. Standart referansları
    ("VW 10500", "ISO 845"), not cümleleri ("410 µm dick"), tolerans ve
    revizyon tablosu satırları ise hep komşulu gelir. 'Pos.' çapası olmayan
    çizimde antet/tablo bölgeleri konumdan bilinemediği için ayrım buradan
    yapılır — yoksa 105 balonun 75'i tablo/başlık sayısı oluyordu.
    """
    dikey = s.get("yon") == "d"
    # Okuma yönündeki eksen: yatay yazıda x, 90° dönük yazıda y
    a0, a1 = (s["y"], s["y"] + s["h"]) if dikey else (s["x"], s["x"] + s["g"])
    kalin = s["g"] if dikey else s["h"]
    # Yazıya dik eksende merkez (aynı satırda mı?)
    dik = (s["x"] + s["g"] / 2) if dikey else (s["y"] + s["h"] / 2)
    for o in hepsi:
        if o is s or o.get("yon") != s.get("yon"):
            continue
        odik = (o["x"] + o["g"] / 2) if dikey else (o["y"] + o["h"] / 2)
        if abs(odik - dik) > kalin * 0.6:
            continue                        # başka satır
        b0, b1 = (o["y"], o["y"] + o["h"]) if dikey else (o["x"], o["x"] + o["g"])
        bosluk = b0 - a1 if b0 >= a1 else a0 - b1
        # Esik DAR tutulur: cumle icindeki kelime araligi (~0,4·h) yakalanir,
        # ayni hizadaki iki AYRI olcu ("17   21", ~1,3·h) korunur.
        if -kalin * 0.2 < bosluk < kalin * 1.0:
            return True
    return False


def _yogun_kumede(s, hepsi, yaricap_kat=5.0, esik=6):
    """Kutu YOĞUN bir kümenin (tablo) içinde mi?

    Genel tolerans tablosu, revizyon tablosu gibi ızgaralarda sayılar küçük
    bir alanda sıkışıktır; çizim üstündeki gerçek ölçüler ise geometriye
    yayılmış ve seyrektir. Hücre içindeki sayının aynı satırda komşusu
    olmadığı için _metin_satirinda onları yakalayamıyor.
    """
    r = max(s["g"], s["h"]) * yaricap_kat
    cx, cy = s["x"] + s["g"] / 2, s["y"] + s["h"] / 2
    n = 0
    for o in hepsi:
        if o is s:
            continue
        ox, oy = o["x"] + o["g"] / 2, o["y"] + o["h"] / 2
        if abs(ox - cx) <= r and abs(oy - cy) <= r:
            n += 1
            if n >= esik:
                return True
    return False


def _cizgili_hucrede(im, s):
    """Kutu, ÜSTÜNDE ve ALTINDA tablo çizgisi olan bir hücrenin içinde mi?

    Revizyon/referans tablolarının gözleri hem üstten hem alttan çizgilidir.
    Çizim üstündeki bir ölçünün ölçü çizgisi olur ama iki yanında birden
    yatay cetvel bulunmaz — tablo gözlerini bu ayırır.
    """
    import numpy as np
    H, W = im.shape
    x0, x1 = max(0, s["x"] - 4), min(W, s["x"] + s["g"] + 4)
    if x1 - x0 < 6:
        return False
    genislik = x1 - x0

    def cizgi(y0, y1):
        y0, y1 = max(0, int(y0)), min(H, int(y1))
        if y1 <= y0:
            return False
        bant = im[y0:y1, x0:x1] < 128
        # Satırın en az %85'i koyu ise orada yatay bir cetvel vardır
        return bool((bant.sum(axis=1) >= genislik * 0.85).any())

    h = max(s["h"], 8)
    return (cizgi(s["y"] - h * 1.4, s["y"] - h * 0.12)
            and cizgi(s["y"] + s["h"] + h * 0.12, s["y"] + s["h"] + h * 1.4))


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
    # Tohum icin kutu basina Tesseract cagriliyor. 'Pos.' capasi olmayan
    # cizimlerde 470+ kutu var ve hepsini okumak dakikalar suruyordu; sablon
    # ogrenmek icin o kadari gereksiz. Yeterli ornek toplanınca durulur.
    KOTA, YETER = 220, 3
    # Tohum adaylari OLCUYE BENZEYEN kutular: 2-5 karakter. Kutu sirasi
    # sayfa duzenine gore geldiginden ilk N kutu bastik/not alani olabiliyor
    # ve hic rakam ornegi toplanmiyordu (0 balon). Kisa kutular one alinir.
    aday = []
    for s in kutular:
        k = len(_karakterler(im, s, etiket, ist, n))
        if 2 <= k <= 5:
            aday.append((k, s))
    aday.sort(key=lambda z: z[0])
    tohum, bakilan = {}, 0
    for _, s in aday:
        if bakilan >= KOTA or (len(tohum) >= 8 and
                               all(len(v) >= YETER for v in tohum.values())):
            break
        bakilan += 1
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


def _metin_mi(im, s):
    """Kutu HARF içeriyor mu? (ölçü değil, not/başlık parçası)

    Geometri elemesinden geçip sayı olarak okunamayan kutuların tamamı
    ölçülerek görüldü: hepsi sözcük parçasıydı ("resist", "acc.", "Date").
    Bunları sarı balonla işaretlemek yanlış — ölçü değiller. Rakam
    beyaz listesi OLMADAN okunur; harf çıkarsa kutu elenir.
    """
    import pytesseract
    from PIL import Image
    pytesseract.pytesseract.tesseract_cmd = TESSERACT
    p = 8
    kirp = im[max(0, s["y"] - p):s["y"] + s["h"] + p,
              max(0, s["x"] - p):s["x"] + s["g"] + p]
    if kirp.size == 0:
        return False
    b = Image.fromarray(kirp)
    if s["yon"] == "d":
        b = b.rotate(-90, expand=True)
    b = b.resize((b.width * 5, b.height * 5), Image.LANCZOS)
    try:
        t = pytesseract.image_to_string(b, config="--psm 7").strip()
    except Exception:
        return False
    return len(re.findall(r"[A-Za-zÄÖÜäöüßÇĞİÖŞÜçğıöşü]", t)) >= 2


def _sayi_kutusu(kar):
    """Kutu SAYI mı yoksa KELİME mi?

    Teknik resimde rakamlar tek boy yazılır. Küçük harfli bir sözcükte
    ('fertig', 'roh') gövde yüksekliği ile büyük harf yüksekliği farklıdır
    (17'ye 22 gibi). Ondalık ayracı bunun dışındadır: rakamın yarısından
    kısa olan bileşen virgül/noktadır.
    """
    if not kar:
        return False
    yuk = sorted(c[3] for c in kar)
    orta = yuk[len(yuk) // 2]
    rakam = [h for h in yuk if h >= orta * 0.5]      # ayraç hariç
    if not rakam:
        return False
    return max(rakam) <= min(rakam) * 1.25


def _sablonla_oku(model, etiket, s, kar, im=None):
    """Karakterleri öğrenilmiş rakam şablonlarıyla okur.
    Rakamın yarısından kısa bileşen ONDALIK AYRACIDIR; rakam gibi
    eşleştirilirse hiçbir şablona uymuyor ve tüm okuma düşüyordu."""
    import cv2
    import numpy as np
    if not model or not kar or not _sayi_kutusu(kar):
        return None
    yuk = sorted(c[3] for c in kar)
    orta = yuk[len(yuk) // 2]
    hane, guven = [], []
    for c in kar:
        if c[3] < orta * 0.5:
            hane.append(".")                 # virgül / nokta
            continue
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
    t = "".join(hane).strip(".")
    if "?" in t or not guven or min(guven) <= 0.55:
        return None
    return t if re.fullmatch(r"\d{1,4}(\.\d{1,2})?", t) else None


def tum_olculer(im, capa, plan_degerleri=(), geometri_ele=False):
    """Çizimdeki tüm ölçü kutuları: [(deger|None, x, y, g, h, kaynak)].
    kaynak: 'plan' (kontrol planıyla doğrulandı) · 'okundu' · None (okunamadı)

    geometri_ele=True: 'Pos.' çapası olmayan çizimlerde kullanılır. Çapa
    yokken hangi yazının ölçü olduğu konumdan bilinemez (bu çizimde 466 yazı
    kutusu var, çoğu not/tablo/başlık). Ayrım GEOMETRİDEN yapılır: ölçü
    çizgisine yaslanan, çizgili tablo gözünde olmayan, çizimin kendi
    referans çemberinde olmayan ve bir yazı satırının parçası olmayan
    kutular ölçüdür.
    """
    import cv2
    import numpy as np
    H, W = im.shape
    kutu = _yakinlari_birlestir(
        [s for s in _yazi_kutulari(im) if not _olcu_disi(s, W, H, capa)])
    siyah0 = (im < 128).astype(np.uint8)
    n0, etiket0, ist0, _ = cv2.connectedComponentsWithStats(siyah0, 8)
    tohum_kutu = list(kutu)              # rakam şablonları TÜM çizimden öğrenilir
    if geometri_ele:
        # Ölçü metni KISADIR ("48", "15,05") ve rakamları TEK BOYdur.
        # 6 karakterden uzun ya da karışık yükseklikli kutu bir KELİMEdir
        # ("Kennzeichnung", "fertig") — ölçü değil, okunamadığı için sarı
        # balon olarak kalıyordu.
        def sayi_gibi(s):
            kar = _karakterler(im, s, etiket0, ist0, n0)
            return 0 < len(kar) <= 6 and _sayi_kutusu(kar)
        kutu = [s for s in kutu if sayi_gibi(s)]
    if geometri_ele:
        # Çapa yokken hangi yazının ölçü olduğu konumdan bilinemez. Ölçüt:
        # (1) yanında ölçü çizgisi VAR, (2) üstü-altı birden çizgili bir
        # tablo gözünde DEĞİL, (3) çizimin kendi referans çemberinin içinde
        # DEĞİL. Yoğunluk elemesi kaldırıldı: ölçü yoğun bölgelerde gerçek
        # ölçüleri de kesiyordu.
        kutu = [s for s in kutu
                if _olcu_cizgisi_var(im, s)
                and not _cizgili_hucrede(im, s)
                and not _cember_icinde(im, s)
                and not _metin_satirinda(s, kutu)]
    plan = {("%g" % float(d)) for d in plan_degerleri}
    siyah, n_bil, etiket, ist = siyah0, n0, etiket0, ist0
    # Şablonlar ÇİZİMİN TAMAMINDAN öğrenilir: ölçü kutuları azken (68) model
    # yalnız 0-6'yı öğrenebiliyor, 7/8/9 içeren ölçüler okunamıyordu.
    # Tablolarda ve notlarda bol rakam var; onlar tohum olarak kullanılır.
    model = rakam_modeli(im, tohum_kutu, etiket, ist, n_bil)
    sonuc = []
    for s in kutu:
        kar = _karakterler(im, s, etiket, ist, n_bil)
        # Okunamayan kutu ATILMAZ: geometri elemesinden gectiyse (olcu
        # cizgisi var, tablo gozu degil, cember degil) o bir olcudur ve
        # SARI balonla isaretlenip degeri rapora elle girilir. Eskiden
        # sessizce dusuruluyordu; 72 olcunun 51'i balonsuz kaliyordu.
        t = _sablonla_oku(model, etiket, s, kar, im) or _kutu_oku(im, s)
        if t is None and geometri_ele and _metin_mi(im, s):
            continue                       # sözcük parçası — ölçü değil
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


# Stok dokümanlarında teknik resmin yanında parça geçmişi, IMDS, test
# raporu, sertifika gibi ONLARCA PDF duruyor. Sırf "ilk PDF" almak
# 700.0.444'te Part History'yi teknik resim sanmaya yol açtı.
CIZIM_DISI = re.compile(
    r"HISTORY|IMDS|PPAP|TEST|REPORT|RAPOR|SGS|MSDS|SERTIF|CERTIF|PACKAG|"
    r"AMBALAJ|PAKET|TALIMAT|FIZIB|RELEASE|COVER|FORM|EMISSION|ODOUR|"
    r"FORMALDEH|DENSITY|WEIGHT|DEGIS|DEVREYE|DATA\s*SHEET|TL\s*\d", re.I)
CIZIM_ADI = re.compile(
    r"TEKN[İI]K\s*RES[İI]M|TECHNICAL\s*DRAWING|DRAWING|ZEICHNUNG|"
    r"^RES[İI]M\b|^TR\b", re.I)
# Zaten numaralandırılmış (balonlanmış) resim: kendi numaralamamızla
# çakışmasın diye düz teknik resim varken tercih edilmez.
NUMARALI_ADI = re.compile(r"NUMBERED|NUMARAL", re.I)


def cizim_yolu(dokumanlar):
    """ERP stok dokümanları arasından TEKNİK RESİM dosyası (raster ya da PDF).
    Seçim belge ADINA göre yapılır; resim dışı belgeler elenir."""
    aday = [(str(d.get("doc_adi") or ""), str(d.get("link") or ""))
            for d in (dokumanlar or []) if str(d.get("link") or "")]

    def dosya(liste):
        # Vektör PDF varsa önce o kullanılır: metin ve çizgiler temiz
        for uzanti in ((".pdf",), (".tif", ".tiff", ".png", ".jpg", ".jpeg")):
            for _, yol in liste:
                if yol.lower().endswith(uzanti):
                    return yol
        return None

    resim = [(a, y) for a, y in aday if CIZIM_ADI.search(a) and not CIZIM_DISI.search(a)]
    for kume in (
            [(a, y) for a, y in resim if not NUMARALI_ADI.search(a)],   # düz teknik resim
            resim,                                                      # numaralı da olur
            [(a, y) for a, y in aday if not CIZIM_DISI.search(a)]):     # parça no adlı belge
        y = dosya(kume)
        if y:
            return y
    return None


def cizim_adi(dokumanlar):
    """Seçilen teknik resmin belge adı + revizyonu (rapor başlıkları için)."""
    yol = cizim_yolu(dokumanlar)
    for d in (dokumanlar or []):
        if str(d.get("link") or "") == yol:
            ad = str(d.get("doc_adi") or "").strip()
            rev = str(d.get("rev_no") or "").strip()
            return (ad + (" / " + rev if rev else "")) if ad else None
    return None


def _yerele_al(yol):
    """Ağ paylaşımındaki dosyayı geçici olarak yerele kopyalar (cv2 UNC'de
    Türkçe/uzun yollarda okuyamıyor)."""
    import hashlib
    import shutil
    import tempfile
    if os.path.exists(yol) and not yol.startswith("\\\\"):
        return yol, False
    uz = os.path.splitext(yol)[1] or ".tiff"
    # Ad YOLUN icerigine gore sabit uretilir. Eskiden hash() kullaniliyordu;
    # Python dize hash'i her surecte farkli oldugu icin onbellek HIC tutmuyor,
    # her calisma dosyayi yeniden kopyaliyordu. Sabit ad ayrica dosya sunucusu
    # gecici olarak erisilemezken onceki kopyayla calismayi surdurmeyi saglar.
    g = os.path.join(tempfile.gettempdir(),
                     "apqp_cizim_%s%s" % (hashlib.md5(yol.encode("utf-8",
                                          "replace")).hexdigest()[:12], uz))
    try:
        if not os.path.exists(g) or os.path.getsize(g) == 0:
            shutil.copy2(yol, g)
        return g, True
    except OSError:
        # Kaynak su an erisilemiyor: daha once alinmis kopya varsa onunla devam
        if os.path.exists(g) and os.path.getsize(g) > 0:
            return g, True
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
    # Her müşterinin çizimi 'Pos.' etiketi kullanmıyor (MAN kullanıyor, VW/
    # SITECH kullanmıyor). Çapa yoksa balonlama iptal EDİLMEZ: çizimdeki tüm
    # ölçüler okuma sırasıyla 1..n numaralanır (PPAP 2.2.1 tam kapsam).
    capa = _capalar(im, sablon) if sablon is not None else []
    capa_no = (numaralari_ata(im, capa, set(pos)) if pos else _serbest_ata(im, capa)) \
        if capa else []
    if not capa and not tam:
        return 0, "pozisyon etiketi bulunamadı", []

    if not tam:
        atama = [(a[0], a[1], a[2], a[3]) for a in capa_no]
        satirlar = []
    else:
        # Dogrulama degerleri: POS'lu satirlar varsa onlardan, yoksa kontrol
        # planindaki TUM olculebilir satirlardan. Bu urunun plani "Olcu 1..12"
        # diye adlandirildigi icin POS kumesi bostu ve okunan hicbir olcu
        # planla eslesmiyordu (hepsi genel toleransa dusuyordu).
        plan_deger = [d[0] for k in pos.values() for d in k] or _plan_degerleri(
            kp_satirlari, kod)
        olcu = tum_olculer(im, capa, plan_deger, geometri_ele=not capa)
        # Her ölçü en yakın pozisyona bağlanır, o grupta okuma sırasıyla numaralanır
        gruplar = {}
        for deger, x, y, g, h, kaynak, yon in olcu:
            gruplar.setdefault(_en_yakin_pos(x, y, capa_no), []).append(
                {"deger": deger, "x": x, "y": y, "g": g, "h": h,
                 "kaynak": kaynak, "yon": yon})
        atama, satirlar = [], []
        sira = 0
        for pno in sorted(gruplar, key=lambda z: (z is None, z)):
            liste = sorted(gruplar[pno], key=lambda o: (o["y"] // 60, o["x"]))
            for i, o in enumerate(liste):
                sira += 1
                # Çapa varsa "Pos.alt no", yoksa düz sıra numarası
                etiket = ("%s.%d" % (pno, i + 1) if pno is not None
                          else (str(sira) if not capa_no else "?.%d" % (i + 1)))
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
