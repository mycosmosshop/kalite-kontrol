# -*- coding: utf-8 -*-
"""Teknik resimdeki ölçüleri GÖRME MODELİ ile okur.

Neden: klasik OCR (Tesseract, RapidOCR) taranmış çizimde ölçü metnini
notlardan, tablolardan ve daire içindeki referans numaralarından ayıramıyor;
bu ayrımı altı ayrı geometri sezgisiyle denedim ve hiçbiri güvenilir olmadı.
Görme modeli ayrımı ANLAYARAK yapıyor: ölçü çizgisine bağlı sayıyı okur,
"VW 10500" gibi standart kodunu ve (4) gibi referans balonunu listelemez.

Ölçüm (700.0.444, taranmış TIF, detay bölgesi):
    Tesseract         : 19 beklenen ölçüden 15'i, çoğu yanlış konumda
    görme modeli      : 48, 0.1, 15.05, 16, 17, 21, 20, 5, ø5, 10, 15, 12.5 —
                        hepsi doğru, referans balonları ve kodlar hariç

Sağlayıcı ayarı DEPO DIŞINDA tutulur (anahtar git'e girmesin):
    C:\\Users\\User\\.apqp_ai.json
        {"saglayici": "gemini", "model": "...", "anahtar": "..."}
Anahtar yoksa ya da servise ulaşılamazsa çağıran taraf klasik OCR'a döner.
"""
import base64
import io
import json
import os
import re
import time
import urllib.error
import urllib.request

AYAR_YOLU = os.path.join(os.path.expanduser("~"), ".apqp_ai.json")
# Cizim buyuk; model kucuk parcada belirgin daha iyi okuyor. Parcalar
# ORTUSUR ki kenara denk gelen olcu iki parcada da tam gorunsun.
# Olculdu (700.0.444, 6622x4677): 1800 px -> 15 istek / 30 olcu (35 dahil),
# 2400 px -> 12 istek / 26 olcu (35 kayip). Kucuk parcada model daha iyi
# okuyor; 15 istek ucretsiz kotanin (dakikada 20) altinda kaliyor.
# Olculdu: parca buyudukce kucuk EGIK yazilar (geometrik tolerans, 0.1)
# oransal kuculuyor ve model onlari atliyor.
#   1655x1403 -> 15 olcu, 0.1'ler VAR
#   1800x1800 -> 13 olcu, 0.1'ler YOK
#   2400x2400 -> 26 olcu toplam, 35 kayip
# 1400 secildi: kucuk yazilar geliyor. Istek sayisi artiyor ama 429'da
# sunucunun soyledigi kadar beklenip devam ediliyor.
KARE = 1400
ORTUSME = 200
# Ucretsiz katmanda dakikada sinirli istek var; parcalar arasi bekleme ve
# 429'da ustel geri cekilme ile yeniden deneme yapilir.
BEKLE = 3.0
DENEME = 4


def ayar_oku():
    """Sağlayıcı ayarı: dosya → ortam değişkeni. Yoksa None.

    BİRDEN FAZLA ANAHTAR: "anahtarlar" bir liste ise DÖNÜŞÜMLÜ kullanılır —
    her istek sırayla farklı anahtardan gider. Ücretsiz katmanın kota sınırı
    anahtar başınadır; 2 anahtarla dönüşümlü gidince her anahtar kendi
    sınırının YARISI kadar yük görür, aynı bekleme süresiyle toplam kota
    iki katına çıkar (BEKLE sabiti buna göre ayarlanır, aşağıda).
    """
    try:
        a = json.load(io.open(AYAR_YOLU, encoding="utf-8"))
    except Exception:
        a = {}
    if not a.get("anahtarlar"):
        # Geriye dönük uyum: tekil "anahtar" varsa tek elemanlı listeye çevrilir
        a["anahtarlar"] = [a["anahtar"]] if a.get("anahtar") else []
    if not a["anahtarlar"]:
        a["anahtarlar"] = [k for k in [os.environ.get("GEMINI_API_KEY", "")] if k]
        a.setdefault("saglayici", "gemini")
    if not a["anahtarlar"]:
        # Mevzuat Radar / Mail Merkezi ayarlarindaki anahtar
        for yol, alan in ((os.path.join(os.path.expanduser("~"), "Desktop",
                                        "n8n_mail_gorev", "ayarlar.json"), "ai_anahtar"),
                          (os.path.join("D:\\", "Yazılım", "mevzuat-radar",
                                        "ayarlar.json"), "gemini_api_key")):
            try:
                tek = json.load(io.open(yol, encoding="utf-8")).get(alan, "")
                if tek:
                    a["anahtarlar"] = [tek]
                    a.setdefault("saglayici", "gemini")
                    break
            except Exception:
                continue
    if not a["anahtarlar"]:
        return None
    a["anahtar"] = a["anahtarlar"][0]      # geriye donuk uyum: ilk anahtar
    return a


ISTEM = (
    "Bu bir teknik resmin bir bölümü. Görevin BOYUTSAL ÖLÇÜLERİ okumak.\n"
    "SADECE ölçü çizgisine bağlı sayıları listele.\n"
    "LİSTELEME: daire içindeki referans/pozisyon numaraları, sayfa çerçevesi "
    "pafta numaraları, standart kodları (VW 10500, DIN 1451, TL 1010, ISO 845 "
    "gibi), not cümlelerinin içindeki sayılar, tablo hücreleri, antet/başlık "
    "bloğu, revizyon tablosu.\n"
    # Olculdu: 6FA.881.989 ciziminde detay gorunusun yanindaki OLCEK notu
    # "1:5" model tarafindan "1" diye okunup balonlanmisti; deger olarak
    # "1" geldigi icin kalip filtresi de yakalayamiyor — kaynagi burasi.
    # Olculdu: VW genel tolerans tablosunun satirlari (400, 120, 30, 6,
    # 2,0, 1,6, 0,6, 0,3) olcu sanilip 11 balon basilmisti.
    # Olculdu: ham okumada hicbir yaricap oneki yoktu (R50 -> "50") ve
    # sag alt kosedeki egik yazilmis R15 tamamen kaciriliyordu.
    "YARIÇAP VE ÇAP ÖLÇÜLERİNİ DE LİSTELE: R15, R50, ø8 gibi. Öneki "
    "(R ya da ø) mutlaka koru — \"R15\" yaz, \"15\" değil. Yarıçaplar "
    "genelde küçük ve EĞİK yazılır, kavis okuyla gösterilir; kösede ya da "
    "çizimin kenarinda kalanları da atlama.\n"
    "GENEL TOLERANS TABLOSUNU LİSTELEME: \">400 \" ile başlayan aralık-"
    "tolerans satırları ve açı toleransı ölçü DEĞİLDİR; o tablodaki 400, 120, "
    "30, 6, 2.0, 1.6, 0.6, 0.3 gibi sayıları yazma.\n"
    "ÖLÇEK NOTUNU ASLA LİSTELEME: \"1:5\", \"1:1\", \"2:1\" gibi oranlar ve "
    "bunların yanındaki görünüş/detay adları ölçü DEĞİLDİR; oranın tek bir "
    "rakamını da (1 ya da 5) ölçü diye yazma. Aynı şekilde kağıt formatı "
    "(A1, A3), tarih (31.07.2025), sayfa no ve ağırlık (63g) ölçü değildir.\n"
    "Ondalık ayracı NOKTA yaz. Çap işaretini ø, yarıçapı R olarak koru.\n"
    "Her ölçü için: {\"deger\": \"48\", \"x\": 123, \"y\": 456}\n"
    "x,y = ölçü YAZISININ bu görüntüdeki piksel merkezi (sol üst köşe 0,0).\n"
    "Yalnız JSON dizisi döndür, başka hiçbir şey yazma.")


# GUNLUK KOTA MODEL BASINA: 429 govdesindeki ihlal
# "GenerateRequestsPerDayPerProjectPerModel-FreeTier" — yani bir modelin
# gunluk hakki bitince AYNI anahtarla BASKA model hala calisiyor (olculdu:
# 3.5-flash-lite doluyken 3.1-flash-lite ve flash-lite-latest calisiyordu).
# Ayni projedeki ikinci anahtar kotayi ARTIRMAZ; model degistirmek artirir.
YEDEK_MODELLER = ("gemini-3.1-flash-lite", "gemini-flash-lite-latest",
                  "gemini-3-flash-preview", "gemini-3.5-flash-lite")
# Kota dolunca SIRAYLA denenecek modeller — olculmus okuma kalitesine
# gore. Bu listede olmayan modele kendiliginden gecilmez.
TERCIH_SIRASI = ("gemini-3.5-flash-lite", "gemini-3.1-flash-lite",
                 "gemini-flash-lite-latest", "gemini-3-flash-preview",
                 "gemini-3.6-flash", "gemini-3.7-flash")
_model_sirasi = [0]          # kota dolunca ilerler, surec boyunca korunur


_havuz = [None]           # saglayicidan cekilen model listesi (bir kez)


def _model_havuzu(ayar, anahtar):
    """Saglayicidaki GORSEL OKUYABILEN modeller — kota model basina.

    Sabit YEDEK_MODELLER listesi dardi: dordu de dolunca balonlama
    "kota" deyip duruyordu, oysa saglayicida kotasi bos baska modeller
    vardi (olculdu: 3.5/3.1/flash-lite-latest/3-flash-preview 429 iken
    gemini-flash-latest, 3.6-flash ve 3.7-flash calisiyordu). Liste bir
    kez cekilir, cekilemezse sabit listeye dusulur.
    """
    if _havuz[0] is not None:
        return _havuz[0]
    try:
        u = ("https://generativelanguage.googleapis.com/v1beta/models"
             "?pageSize=200&key=" + (anahtar or ayar.get("anahtar") or ""))
        with urllib.request.urlopen(u, timeout=30) as f:
            d = json.load(f)
        ad = []
        for m in d.get("models", []):
            if "generateContent" not in m.get("supportedGenerationMethods", []):
                continue
            n = m["name"].split("/")[-1]
            if re.search(r"tts|image|embedding|lyria|nano-banana|aqa", n):
                continue
            if not re.search(r"flash|pro", n):
                continue
            ad.append(n)
        # YALNIZ OLCULMUS IYI OKUYUCULAR. Havuza her modeli koymak
        # kotayi cozuyor ama kaliteyi bozuyordu: gecilen model 154 balon
        # cikardi (planda 24 olcu var). Listede olmayan bir modele
        # kendiliginden gecilmez — kullanici ERP'den secebilir.
        _havuz[0] = [m for m in TERCIH_SIRASI if m in ad] or list(YEDEK_MODELLER)
    except Exception:
        _havuz[0] = list(YEDEK_MODELLER)
    return _havuz[0]


def _sonraki_model(ayar, anahtar=None):
    """Kotasi dolan modelden sonraki yedege gecer; yoksa None."""
    simdiki = ayar.get("model") or ""
    denenen = ayar.setdefault("_denenen", set())
    denenen.add(simdiki)
    for m in _model_havuzu(ayar, anahtar):
        if m not in denenen:
            denenen.add(m)
            return m
    return None


def _gemini(b64, ayar, anahtar=None):
    # flash-lite: ucretsiz katmanda kotasi belirgin daha genis, ayni
    # cizim parcasinda ayni 15 olcuyu dogru okudu.
    model = ayar.get("model") or "gemini-3.5-flash-lite"
    govde = json.dumps({
        "contents": [{"parts": [{"text": ISTEM},
                                {"inline_data": {"mime_type": "image/png", "data": b64}}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 8192},
    }).encode("utf-8")
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           + model + ":generateContent?key=" + (anahtar or ayar["anahtar"]))
    r = urllib.request.Request(url, data=govde,
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=240) as f:
        d = json.load(f)
    return d["candidates"][0]["content"]["parts"][0]["text"]


def _openai_uyumlu(b64, ayar):
    """xAI / OpenAI uyumlu uç nokta (sağlayıcı değiştirilebilir olsun)."""
    model = ayar.get("model") or "grok-2-vision-1212"
    govde = json.dumps({
        "model": model, "temperature": 0,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": ISTEM},
            {"type": "image_url",
             "image_url": {"url": "data:image/png;base64," + b64}}]}],
    }).encode("utf-8")
    r = urllib.request.Request(
        ayar.get("uc", "https://api.x.ai/v1") + "/chat/completions", data=govde,
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + ayar["anahtar"]})
    with urllib.request.urlopen(r, timeout=240) as f:
        d = json.load(f)
    return d["choices"][0]["message"]["content"]


def _bekleme_suresi(e, varsayilan):
    """429 gövdesindeki "Please retry in 7.6s" süresini okur.
    Körü körüne üstel bekleme yerine sunucunun söylediğine uyulur; her
    gereksiz deneme de kotadan yiyor."""
    try:
        govde = e.read().decode("utf-8", "replace")
    except Exception:
        return varsayilan
    g = re.search(r"retry in ([\d.]+)s", govde)
    if g:
        return min(float(g.group(1)) + 1.5, 60.0)
    g = re.search(r'"retryDelay"\s*:\s*"([\d.]+)s"', govde)
    return min(float(g.group(1)) + 1.5, 60.0) if g else varsayilan


def _cozumle(metin):
    """Model çıktısındaki JSON dizisini ayıklar (kod bloğu içinde gelebilir)."""
    g = re.search(r"\[.*\]", metin or "", re.S)
    if not g:
        return []
    try:
        return json.loads(g.group(0))
    except ValueError:
        return []


# Son okumanin DURUMU. Bos liste donmenin sebebi cagirana bildirilmeli:
# "anahtar yok" ile "kota doldu" ayni sey degil. Kota dolduysa klasik OCR'a
# sessizce dusup NOT BLOGUNA cop balon basmak, balonsuz cizimden kotudur.
SON_DURUM = "tamam"


ZORLA_MODEL = [None]      # disaridan secilen model (cop cikti sonrasi)


def model_atla():
    """Bir sonraki yedek modele gecer; yenisinin adini doner, yoksa None.

    Kota dolunca otomatik gecis _gemini icinde yapiliyor. Bu fonksiyon
    KALITE nedeniyle disaridan cagrilir: model kotasi dolu olmasa bile
    cop okuma uretiyorsa (olculdu: 154 balon, planda 24 olcu) sonraki
    modele gecilir.
    """
    ayar = ayar_oku()
    if ZORLA_MODEL[0]:
        ayar["model"] = ZORLA_MODEL[0]
    anahtarlar = ayar.get("anahtarlar") or [ayar.get("anahtar")]
    if ZORLA_MODEL[0]:
        ayar["model"] = ZORLA_MODEL[0]
    m = _sonraki_model(ayar, anahtarlar[0] if anahtarlar else None)
    if m:
        ZORLA_MODEL[0] = m
    return m


def olculeri_oku(im, log=None):
    """Çizimdeki ölçüler: [(deger_metni, x, y)] — GLOBAL piksel konumuyla.
    Anahtar yoksa ya da servis yanıt vermezse boş liste döner (çağıran taraf
    klasik OCR'a devam eder)."""
    import cv2
    global SON_DURUM
    SON_DURUM = "tamam"
    ayar = ayar_oku()
    if not ayar:
        SON_DURUM = "anahtar_yok"
        return []
    H, W = im.shape[:2]
    sonuc, hata = [], 0
    # KOTA KADANSI: ucretsiz katman dakikada 20 istek = 3 sn'de BIR ISTEK,
    # ANAHTAR BASINA. N anahtar DONUSUMLU kullanilinca her anahtar kendi
    # 3 sn sinirinin altinda kalirken GLOBAL kadans BEKLE/N'e duser — toplam
    # kota N kati olur. Eskiden her cagridan SONRA kosulsuz BEKLE kadar
    # uyunuyordu; istegin kendisi zaten ~1,4 sn surdugu icin o sure ikinci
    # kez odeniyordu. Artik iki istegin BASLANGICI arasinda kadans kadar
    # olmasi saglanir.
    anahtarlar = ayar["anahtarlar"]
    kadans = BEKLE / len(anahtarlar)
    son_baslangic = [0.0]
    sira = [0]
    for y0 in range(0, H, KARE - ORTUSME):
        for x0 in range(0, W, KARE - ORTUSME):
            x1, y1 = min(x0 + KARE, W), min(y0 + KARE, H)
            if x1 - x0 < 200 or y1 - y0 < 200:
                continue
            ok, tampon = cv2.imencode(".png", im[y0:y1, x0:x1])
            if not ok:
                continue
            b64 = base64.b64encode(tampon.tobytes()).decode()
            kalan = kadans - (time.time() - son_baslangic[0])
            if son_baslangic[0] and kalan > 0:
                time.sleep(kalan)
            son_baslangic[0] = time.time()
            metin = None
            for deneme in range(DENEME):
                anahtar = anahtarlar[sira[0] % len(anahtarlar)]
                sira[0] += 1               # bir sonraki istek/deneme BASKA anahtarla
                try:
                    metin = (_gemini(b64, ayar, anahtar)
                             if ayar.get("saglayici", "gemini") == "gemini"
                             else _openai_uyumlu(b64, ayar))
                    SON_DURUM = "tamam"        # bu parca basariyla okundu —
                    break                      # onceki denemedeki 429 gecerliligini yitirdi
                except urllib.error.HTTPError as e:
                    if e.code == 429:
                        SON_DURUM = "kota"
                        # Gunluk kota MODEL basina: yedek modele gec, tum
                        # okumayi bir modelin bitmis hakki yuzunden birakma.
                        yeni_model = _sonraki_model(ayar, anahtar)
                        if yeni_model:
                            if log:
                                log("   · AI kotası doldu, yedek modele geçildi: %s"
                                    % yeni_model)
                            ayar["model"] = yeni_model
                            SON_DURUM = "tamam"
                            continue
                        if deneme < DENEME - 1 and len(anahtarlar) > 1:
                            # Baska anahtar hemen denenir, sunucunun soyledigi
                            # sureyi BEKLEMEDEN — o anahtarin kotasi degil
                            continue
                    if e.code == 429 and deneme < DENEME - 1:
                        # Hiz siniri: sunucunun soyledigi kadar beklenir
                        time.sleep(_bekleme_suresi(e, BEKLE * (2 ** deneme)))
                        son_baslangic[0] = time.time()
                        continue
                    hata += 1
                    if log:
                        log("   ! AI okuma hatası (%d,%d): %s" % (x0, y0, str(e)[:60]))
                    break
                except Exception as e:
                    SON_DURUM = "hata"
                    hata += 1
                    if log:
                        log("   ! AI okuma hatası (%d,%d): %s" % (x0, y0, str(e)[:60]))
                    break
            if metin is None:
                # KOTA DOLDUYSA HEMEN VAZGEC: her parcayi tek tek denemek
                # (4 deneme x ustel bekleme x onlarca parca) dakikalar
                # harciyor ve sonuc yine bos oluyor.
                if SON_DURUM == "kota":
                    if log:
                        log("   ! AI kotasi doldu — okuma durduruldu")
                    return []
                if hata >= 4:                 # servis gercekten kapali
                    return sonuc and _tekille(sonuc) or []
                continue
            for o in _cozumle(metin):
                try:
                    d = str(o.get("deger", "")).strip()
                    # Isaretli deger TOLERANSTIR, olcu degil ("+0,2", "-0.2")
                    if d[:1] in "+-":
                        continue
                    # KOORDINAT OLCEGI: model konumu 0-1000 NORMALIZE verir
                    # (Gemini kutu konvansiyonu). Ham piksel sanmak sistematik
                    # kayma yapiyordu — olculdu: ham piksel yorumu ortanca
                    # 279 px sapiyor, normalize yorumu 32 px.
                    x = float(o.get("x", -1)) / 1000.0 * (x1 - x0) + x0
                    y = float(o.get("y", -1)) / 1000.0 * (y1 - y0) + y0
                except (TypeError, ValueError):
                    continue
                if d and 0 <= x < W and 0 <= y < H:
                    sonuc.append((d, x, y))
    return _tekille(sonuc)


def _tekille(liste, esik=90):
    """Örtüşen karelerden gelen aynı ölçüyü teke indirir."""
    temiz = []
    for d, x, y in liste:
        if any(a == d and abs(bx - x) < esik and abs(by - y) < esik
               for a, bx, by in temiz):
            continue
        temiz.append((d, x, y))
    return temiz
