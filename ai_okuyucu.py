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
    """Sağlayıcı ayarı: dosya → ortam değişkeni. Yoksa None."""
    try:
        a = json.load(io.open(AYAR_YOLU, encoding="utf-8"))
    except Exception:
        a = {}
    if not a.get("anahtar"):
        a["anahtar"] = os.environ.get("GEMINI_API_KEY", "")
        a.setdefault("saglayici", "gemini")
    if not a.get("anahtar"):
        # Mevzuat Radar / Mail Merkezi ayarlarindaki anahtar
        for yol, alan in ((os.path.join(os.path.expanduser("~"), "Desktop",
                                        "n8n_mail_gorev", "ayarlar.json"), "ai_anahtar"),
                          (os.path.join("D:\\", "Yazılım", "mevzuat-radar",
                                        "ayarlar.json"), "gemini_api_key")):
            try:
                a["anahtar"] = json.load(io.open(yol, encoding="utf-8")).get(alan, "")
                if a["anahtar"]:
                    a.setdefault("saglayici", "gemini")
                    break
            except Exception:
                continue
    return a if a.get("anahtar") else None


ISTEM = (
    "Bu bir teknik resmin bir bölümü. Görevin BOYUTSAL ÖLÇÜLERİ okumak.\n"
    "SADECE ölçü çizgisine bağlı sayıları listele.\n"
    "LİSTELEME: daire içindeki referans/pozisyon numaraları, sayfa çerçevesi "
    "pafta numaraları, standart kodları (VW 10500, DIN 1451, TL 1010, ISO 845 "
    "gibi), not cümlelerinin içindeki sayılar, tablo hücreleri, antet/başlık "
    "bloğu, revizyon tablosu.\n"
    "Ondalık ayracı NOKTA yaz. Çap işaretini ø, yarıçapı R olarak koru.\n"
    "Her ölçü için: {\"deger\": \"48\", \"x\": 123, \"y\": 456}\n"
    "x,y = ölçü YAZISININ bu görüntüdeki piksel merkezi (sol üst köşe 0,0).\n"
    "Yalnız JSON dizisi döndür, başka hiçbir şey yazma.")


def _gemini(b64, ayar):
    # flash-lite: ucretsiz katmanda kotasi belirgin daha genis, ayni
    # cizim parcasinda ayni 15 olcuyu dogru okudu.
    model = ayar.get("model") or "gemini-3.5-flash-lite"
    govde = json.dumps({
        "contents": [{"parts": [{"text": ISTEM},
                                {"inline_data": {"mime_type": "image/png", "data": b64}}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 8192},
    }).encode("utf-8")
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           + model + ":generateContent?key=" + ayar["anahtar"])
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


def olculeri_oku(im, log=None):
    """Çizimdeki ölçüler: [(deger_metni, x, y)] — GLOBAL piksel konumuyla.
    Anahtar yoksa ya da servis yanıt vermezse boş liste döner (çağıran taraf
    klasik OCR'a devam eder)."""
    import cv2
    ayar = ayar_oku()
    if not ayar:
        return []
    H, W = im.shape[:2]
    sonuc, hata = [], 0
    for y0 in range(0, H, KARE - ORTUSME):
        for x0 in range(0, W, KARE - ORTUSME):
            x1, y1 = min(x0 + KARE, W), min(y0 + KARE, H)
            if x1 - x0 < 200 or y1 - y0 < 200:
                continue
            ok, tampon = cv2.imencode(".png", im[y0:y1, x0:x1])
            if not ok:
                continue
            b64 = base64.b64encode(tampon.tobytes()).decode()
            metin = None
            for deneme in range(DENEME):
                try:
                    metin = (_gemini(b64, ayar)
                             if ayar.get("saglayici", "gemini") == "gemini"
                             else _openai_uyumlu(b64, ayar))
                    break
                except urllib.error.HTTPError as e:
                    if e.code == 429 and deneme < DENEME - 1:
                        # Hiz siniri: sunucunun soyledigi kadar beklenir
                        time.sleep(_bekleme_suresi(e, BEKLE * (2 ** deneme)))
                        continue
                    hata += 1
                    if log:
                        log("   ! AI okuma hatası (%d,%d): %s" % (x0, y0, str(e)[:60]))
                    break
                except Exception as e:
                    hata += 1
                    if log:
                        log("   ! AI okuma hatası (%d,%d): %s" % (x0, y0, str(e)[:60]))
                    break
            if metin is None:
                if hata >= 4:                 # servis gercekten kapali
                    return sonuc and _tekille(sonuc) or []
                continue
            time.sleep(BEKLE)                 # sonraki parcaya kadar nefes
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
