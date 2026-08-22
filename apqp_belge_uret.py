# -*- coding: utf-8 -*-
"""APQP kanit belgelerini urunun ERP verisinden uretir.

  python apqp_belge_uret.py <stok kodu>

Uretilenler (G:\\Drive'im\\APQP\\<kod>\\ altina):
  PL74 Proses Akis Diyagrami   - sablon kopyalanip doldurulur
  FR90 Fizibilite Taahhudu     - sablon kopyalanip doldurulur
  FR81 Toplanti Tutanagi       - sifirdan uretilir (sablon yok)
  Kapasite Takip Formu         - sifirdan uretilir (sablon yok)

ONEMLI: Sablonlarda otomatik sekiller (41 adete varan rect/diamond/line) ve
gomulu gorseller var; openpyxl bir dosyayi acip kaydettiginde bu sekilleri
KAYBEDIYOR. Bu yuzden sablonlar ZIP DUZEYINDE yamaniyor: yalniz ilgili sayfa
XML'indeki hucre degerleri degistiriliyor, geri kalan her sey (sekiller,
gorseller, makrolar, stiller) bit bit korunuyor.
"""
import sys, re, io, json, zipfile, shutil, urllib.request, urllib.parse, datetime, os

SUPABASE = "https://nnubrxbpthmkitueixbh.supabase.co/rest/v1"
ANON = ("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5udWJyeGJwdGhta2l0"
        "dWVpeGJoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODA1NjI2MDIsImV4cCI6MjA5NjEzODYwMn0"
        ".CHZUOylf_q8kkOQbFf9VWZ6-doUTlynmAhahM2EuImE")
DRIVE = r"G:\Drive'ım\APQP"
SABLON = os.path.join(DRIVE, "205.0.214-C")     # ornek/kaynak belge seti

# Lokasyona gore APQP ekibi (FR91 sablonundaki roller)
EKIP = {
    "ankara": [("AR&GE Proje Yöneticisi", "Sinem Kaya"), ("Kalite Güvence Müdürü", "Volkan Pekatik"),
               ("Kalite Mühendisi", "Emre Biçer"), ("Satın Alma", "Kutlay Altıparmak"),
               ("Lojistik", "Taner Şeşenoğlu"), ("Üretim", "Mete Yılmaz"), ("Satış", "Ender Zaimoğlu")],
    "cerkezkoy": [("AR&GE Proje Yöneticisi", "Sinem Kaya"), ("Kalite Güvence Müdürü", "Volkan Pekatik"),
                  ("Kalite Mühendisi", "Emrah Eryılmaz"), ("Satın Alma", "Kutlay Altıparmak"),
                  ("Lojistik", "Necmettin Altıntaş"), ("Üretim", "Umut Çiftçiogulları"),
                  ("Satış", "Ender Zaimoğlu")],
}


def sorgu(yol):
    r = urllib.request.Request(SUPABASE + yol, headers={"apikey": ANON, "Authorization": "Bearer " + ANON})
    with urllib.request.urlopen(r, timeout=60) as f:
        return json.load(f)


def met(x):
    return "" if x is None else str(x).strip()


# ── XLSX zip yamasi: hucre degerini degistirir, gerisine dokunmaz ─────────
def _xml_kacir(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _sutun(ref):
    return re.match(r"([A-Z]+)", ref).group(1)


def _sutun_no(h):
    n = 0
    for c in h:
        n = n * 26 + (ord(c) - 64)
    return n


def hucre_yaz(kaynak, hedef, sayfa_dosyasi, degerler):
    """degerler: {'C6': 'metin', 'B12': 3, ...}  -> hedef dosyaya yazar."""
    zin = zipfile.ZipFile(kaynak)
    xml = zin.read(sayfa_dosyasi).decode("utf-8")

    for ref, deger in degerler.items():
        sayi = isinstance(deger, (int, float))
        icerik = (('<v>%s</v>' % deger) if sayi
                  else ('<is><t xml:space="preserve">%s</t></is>' % _xml_kacir(str(deger))))
        tip = "" if sayi else ' t="inlineStr"'
        # Var olan hucre (kendi kendini kapatan ya da normal)
        kalip = re.compile(r'<c r="%s"([^>/]*)(/>|>.*?</c>)' % ref, re.S)
        m = kalip.search(xml)
        if m:
            oz = re.sub(r'\st="[^"]*"', "", m.group(1))
            xml = xml[:m.start()] + '<c r="%s"%s%s>%s</c>' % (ref, oz, tip, icerik) + xml[m.end():]
            continue
        # Hucre yok: satiri bul, sutun sirasina gore ekle
        satir_no = ref[len(_sutun(ref)):]
        sm = re.search(r'(<row r="%s"[^>]*>)(.*?)(</row>)' % satir_no, xml, re.S)
        if not sm:
            print("   ! satir yok, atlandi:", ref)
            continue
        ic = sm.group(2)
        yeni = '<c r="%s"%s>%s</c>' % (ref, tip, icerik)
        yer = len(ic)
        for cm in re.finditer(r'<c r="([A-Z]+)\d+"', ic):
            if _sutun_no(cm.group(1)) > _sutun_no(_sutun(ref)):
                yer = cm.start()
                break
        xml = xml[:sm.start(2)] + ic[:yer] + yeni + ic[yer:] + xml[sm.end(2):]

    zout = zipfile.ZipFile(hedef, "w", zipfile.ZIP_DEFLATED)
    for e in zin.infolist():
        zout.writestr(e, xml.encode("utf-8") if e.filename == sayfa_dosyasi else zin.read(e.filename))
    zout.close()
    zin.close()


# ── ERP verisi ───────────────────────────────────────────────────────────
def urun_verisi(kod):
    k = urllib.parse.quote(kod)
    plan = sorgu("/leansys_kontrol_plani?stok_kodu=eq.%s&select=stok_adi,cari_adi,tr_revtarih&limit=200" % k)
    rota = sorgu("/operasyon_kartlari?stok_kodu=eq.%s&select=op_no,makine_adi,makine_kodu,std_zaman,"
                 "kapasite,kapasite_sure,personel,talimat,kayit_tarihi,varsayilan,header_id&order=op_no" % k)
    # Bir urunun birden fazla ROTASI olabilir (farkli lokasyon/hat). Yalniz
    # VARSAYILAN rota alinir; yoksa ilk rota. Karistirilirsa akis diyagramina
    # Eskisehir ve Cerkezkoy makineleri birlikte duser.
    if rota:
        hid = next((r.get("header_id") for r in rota if r.get("varsayilan") is True), rota[0].get("header_id"))
        rota = [r for r in rota if r.get("header_id") == hid]
    agac = sorgu("/urun_agaclari?urun_kodu=eq.%s&select=tuketim_kodu,tuketim_adi,miktar,birim,cinsi" % k)
    dok = sorgu("/stok_dokumanlari?stok_kodu=eq.%s&select=doc_adi,rev_no,link" % k)
    if not plan and not rota:
        raise SystemExit("ERP'de bu ürün bulunamadı: " + kod)
    mak = " ".join(met(r.get("makine_adi")) for r in rota).upper()
    lokasyon = "ankara" if "(ANK" in mak else "cerkezkoy"
    devreye = met((rota[0] if rota else {}).get("kayit_tarihi"))[:10] or \
              met(next((p for p in plan if met(p.get("tr_revtarih"))), {}).get("tr_revtarih"))[:10] or \
              datetime.date.today().isoformat()
    return {
        "kod": kod,
        "ad": met((plan[0] if plan else {}).get("stok_adi")) or kod,
        "musteri": met((plan[0] if plan else {}).get("cari_adi")),
        "rota": rota, "agac": agac, "dok": dok,
        "lokasyon": lokasyon, "devreye": devreye,
        "ekip": EKIP[lokasyon],
    }


# ── PL74 Proses Akış Diyagramı ───────────────────────────────────────────
# Şablon kopyalanıp doldurulur; akış adımları operasyon kartından gelir,
# başa girdi kontrol/depolama, sona depolama/sevkiyat eklenir (örnekteki
# 36.72010-6345 akışının kendi düzeni).
def pl74(v, hedef):
    kaynak = os.path.join(SABLON, "Flow Diagram.xlsx")
    adimlar = [(0, "Hammadde Temini - Giriş Kalite Kontrol"), (0, "Hammadde Depolama")]
    gorulen = set()
    for r in v["rota"]:
        ad = met(r.get("makine_adi"))
        if not ad or ad in gorulen:
            continue
        gorulen.add(ad)
        adimlar.append((int(met(r.get("op_no")) or 0), ad))   # makine adi oldugu gibi (LMM, KP10 kisaltmalari bozulmasin)
    son_op = max([a[0] for a in adimlar if isinstance(a[0], int)] or [0])
    adimlar += [(son_op, "Depolama"), ("", "Sevkiyat")]

    d = {"B6": v["musteri"], "B7": v["ad"] + " / " + v["kod"],
         "B8": "Sanifoam Endüstri ve Tüketim Ürünleri San. Tic. A.Ş."}
    for i, (no, ad) in enumerate(adimlar[:9]):          # şablonda 12–20. satırlar
        d["B%d" % (12 + i)] = no
        d["G%d" % (12 + i)] = ad
    for i in range(len(adimlar), 9):                    # artan satırları temizle
        d["B%d" % (12 + i)] = ""
        d["G%d" % (12 + i)] = ""
    hucre_yaz(kaynak, hedef, "xl/worksheets/sheet1.xml", d)
    return len(adimlar)


# ── FR90 Fizibilite Taahhüdü ─────────────────────────────────────────────
# Şablon kopyalanıp başlık alanları doldurulur. Cevap işaretleri (Evet/Şartlı/
# Hayır) EKİBİN kararıdır — üretim onları DOLDURMAZ, örnekteki işaretler
# şablonla birlikte gelir ve ekip gözden geçirir.
def fr90(v, hedef):
    kaynak = os.path.join(SABLON, "FR90 Fizibilite Taahhüdü.xlsm")
    hammadde = "; ".join((met(a.get("tuketim_kodu")) + " " + met(a.get("tuketim_adi")))[:44]
                         for a in v["agac"][:6]) or "—"
    resim = next((met(x.get("doc_adi")) for x in v["dok"] if met(x.get("link"))), "—")
    d = {"C6": v["musteri"], "H6": v["devreye"],
         "C8": v["ad"], "C10": v["kod"], "C12": resim,
         "L29": hammadde}
    hucre_yaz(kaynak, hedef, "xl/worksheets/sheet1.xml", d)


# ── FR81 Toplantı Tutanağı (şablon yok — Sanifoam antet düzeninde üretilir) ──
# Konular APQP başlangıç toplantısının standart gündemi: altyapı/ekipman,
# tedarikçi, şartname, teknik resim, benzer parça geçmişi, fizibilite.
def fr81(v, hedef):
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
    from openpyxl.utils import get_column_letter

    ince = Side(style="thin", color="808080")
    kenar = Border(left=ince, right=ince, top=ince, bottom=ince)
    wb = Workbook(); ws = wb.active; ws.title = "Toplantı Tutanağı"
    for h, g in zip("ABCDE", (6, 62, 20, 14, 34)):
        ws.column_dimensions[h].width = g

    ws["A1"] = "SaniFoam"; ws["A1"].font = Font(size=18, bold=True)
    ws["B1"] = "TOPLANTI TUTANAĞI"
    ws["B1"].font = Font(size=20, bold=True); ws["B1"].alignment = Alignment(horizontal="center")
    ws["A2"] = "SÜNGER SAN.TİC.A.Ş."; ws["A2"].font = Font(size=8)
    for i, (e, d) in enumerate([("DOK.NO", "FR 81"), ("Y.TRH", "01.09.2004"),
                                ("REV.NO", "00"), ("SAYFA", "1 / 1")]):
        ws.cell(1 + i, 4, e).font = Font(size=9, bold=True)
        ws.cell(1 + i, 5, d).font = Font(size=9)

    ws["A5"] = "TOPLANTI TARİHİ :"; ws["A5"].font = Font(bold=True)
    ws["B5"] = v["devreye_baslangic"]
    ws["C5"] = "TOPLANTI SAATİ :"; ws["C5"].font = Font(bold=True)
    ws["D5"] = "14:00"
    ws["A6"] = "KONU :"; ws["A6"].font = Font(bold=True)
    ws["B6"] = "%s (%s) — APQP başlangıç / fizibilite değerlendirmesi" % (v["ad"], v["kod"])
    ws["A7"] = "KATILIMCILAR :"; ws["A7"].font = Font(bold=True)
    ws["B7"] = ", ".join("%s (%s)" % (ad, rol) for rol, ad in v["ekip"])
    ws["B7"].alignment = Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[7].height = 30

    basliklar = ["NO", "KONU", "SORUMLU", "TERMİN", "AÇIKLAMA"]
    for i, b in enumerate(basliklar):
        c = ws.cell(9, 1 + i, b)
        c.font = Font(bold=True); c.alignment = Alignment(horizontal="center")
        c.fill = PatternFill("solid", fgColor="DCE6F1"); c.border = kenar

    hammadde = ", ".join(met(a.get("tuketim_kodu")) for a in v["agac"][:5]) or "ürün ağacında hammadde yok"
    makineler = ", ".join(sorted({met(r.get("makine_adi")) for r in v["rota"] if met(r.get("makine_adi"))})) or "—"
    rolAd = dict((r, a) for r, a in v["ekip"])
    gundem = [
        ("Müşteri teknik resmi ve şartnamelerin incelenmesi (%s)" % v["resim"],
         rolAd["AR&GE Proje Yöneticisi"], "Teknik resim ve şartname ERP stok dokümanlarında kayıtlı"),
        ("Özel/kritik karakteristiklerin belirlenmesi",
         rolAd["Kalite Güvence Müdürü"], "Kontrol planındaki özel karakteristikler PFMEA'ya aktarılacak"),
        ("Altyapı, ekipman ve tesis yeterliliği değerlendirmesi",
         rolAd["Üretim"], "Kullanılacak hat: %s" % makineler[:120]),
        ("Ölçüm/test ekipmanı ve kalibrasyon ihtiyacı",
         rolAd["Kalite Mühendisi"], "Kontrol planındaki ölçüm yöntemleri için ekipman uygunluğu"),
        ("Hammadde ve alt tedarikçi durumu",
         rolAd["Satın Alma"], "Ürün ağacı: %s — tedarikçiler onaylı tedarikçi listesinden seçilecek" % hammadde[:90]),
        ("Benzer/karşılaştırılabilir parça geçmişi",
         rolAd["AR&GE Proje Yöneticisi"], v["benzer"]),
        ("Kapasite değerlendirmesi (ilk)",
         rolAd["Üretim"], "Darboğaz operasyon ve vardiya kapasitesi Kapasite Takip Formunda"),
        ("Ambalaj ve lojistik planı",
         rolAd["Lojistik"], "FR228 Ambalaj Standardı Formu hazırlanacak"),
        ("Fizibilite kararı (FR90)",
         rolAd["Kalite Güvence Müdürü"], "FR90 Fizibilite Taahhüdü ekip tarafından imzalanacak"),
    ]
    for i, (konu, sorumlu, aciklama) in enumerate(gundem):
        r = 10 + i
        for j, deger in enumerate([i + 1, konu, sorumlu, v["termin"], aciklama]):
            c = ws.cell(r, 1 + j, deger)
            c.border = kenar
            c.alignment = Alignment(wrap_text=True, vertical="center",
                                    horizontal="center" if j in (0, 2, 3) else "left")
            if j == 1:
                c.font = Font(size=10)
        ws.row_dimensions[r].height = 32
    wb.save(hedef)
    return len(gundem)


# ── Kapasite Takip Formu (şablon yok — Run@Rate mantığında üretilir) ──────
# Operasyon kartındaki std_zaman / kapasite / kapasite_sure gerçek verisinden
# hesaplanır. Darboğaz = en düşük vardiya kapasitesi olan operasyon.
def kapasite(v, hedef):
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill

    ince = Side(style="thin", color="808080")
    kenar = Border(left=ince, right=ince, top=ince, bottom=ince)
    wb = Workbook(); ws = wb.active; ws.title = "Kapasite"
    for h, g in zip("ABCDEFGH", (7, 34, 13, 13, 13, 13, 13, 26)):
        ws.column_dimensions[h].width = g

    ws["A1"] = "SaniFoam"; ws["A1"].font = Font(size=16, bold=True)
    ws["B1"] = "KAPASİTE TAKİP FORMU"
    ws["B1"].font = Font(size=16, bold=True); ws["B1"].alignment = Alignment(horizontal="center")
    for i, (e, d) in enumerate([("DOK.NO", "FR 24-K"), ("Y.TRH", datetime.date.today().strftime("%d.%m.%Y")),
                                ("REV.NO", "00"), ("SAYFA", "1 / 1")]):
        ws.cell(1 + i, 7, e).font = Font(size=9, bold=True)
        ws.cell(1 + i, 8, d).font = Font(size=9)

    for i, (e, d) in enumerate([("Parça Kodu:", v["kod"]), ("Parça Adı:", v["ad"]),
                                ("Müşteri:", v["musteri"]), ("Lokasyon:", v["lokasyon_ad"]),
                                ("Vardiya Süresi:", "%s %s (%.2f saat)" % (v["vardiya_sure"], v["birim"], v["vardiya_saat"]))]):
        ws.cell(4 + i, 1, e).font = Font(bold=True)
        ws.cell(4 + i, 2, d)

    basliklar = ["Op", "Operasyon / Makine", "Std. Zaman (%s)" % v["birim"], "Personel",
                 "Vardiya (%s)" % v["birim"], "Vardiya Kap. (adet)", "Günlük (3 vardiya)", "Not"]
    for i, b in enumerate(basliklar):
        c = ws.cell(10, 1 + i, b)
        c.font = Font(bold=True, size=10); c.alignment = Alignment(horizontal="center", wrap_text=True)
        c.fill = PatternFill("solid", fgColor="DCE6F1"); c.border = kenar

    satir = 11
    for op in v["kapasite_satirlari"]:
        for j, deger in enumerate([op["op"], op["makine"], op["std"], op["personel"],
                                   op["sure"], op["kap"], op["gunluk"], op["not"]]):
            c = ws.cell(satir, 1 + j, deger)
            c.border = kenar
            c.alignment = Alignment(horizontal="center" if j != 1 and j != 7 else "left", wrap_text=True)
            if op["darbogaz"]:
                c.fill = PatternFill("solid", fgColor="FDE9D9")
                c.font = Font(bold=True)
        satir += 1

    satir += 1
    ws.cell(satir, 1, "DARBOĞAZ").font = Font(bold=True)
    ws.cell(satir, 2, v["darbogaz"]["makine"]).font = Font(bold=True)
    ws.cell(satir, 6, v["darbogaz"]["kap"]).font = Font(bold=True)
    ws.cell(satir, 7, v["darbogaz"]["gunluk"]).font = Font(bold=True)
    ws.cell(satir, 8, "Hattın kapasitesi bu operasyonla sınırlıdır")
    ws.cell(satir + 2, 1, "Kaynak: LeanSys operasyon kartı (std_zaman / kapasite / kapasite_sure). "
                          "Kapasite = vardiya süresi ÷ standart zaman.").font = Font(size=9, italic=True)
    wb.save(hedef)
    return len(v["kapasite_satirlari"])


# ── Türetilen alanlar ────────────────────────────────────────────────────
def zenginlestir(v):
    v["lokasyon_ad"] = "Ankara" if v["lokasyon"] == "ankara" else "Çerkezköy"
    v["resim"] = next((met(x.get("doc_adi")) + (" / " + met(x.get("rev_no")) if met(x.get("rev_no")) else "")
                       for x in v["dok"] if met(x.get("link"))), "teknik resim ERP'de kayıtlı değil")
    d = datetime.date.fromisoformat(v["devreye"])
    v["devreye_baslangic"] = (d - datetime.timedelta(days=100)).isoformat()   # APQP başlangıcı
    v["termin"] = (d - datetime.timedelta(days=86)).isoformat()               # bölüm 2 termini

    # Benzer parça: aynı kök koddan türeyen ürünler (205.0.214-C -> 205.0.214)
    kok = re.sub(r"[-.][A-Za-z0-9]+$", "", v["kod"])
    try:
        benzer = sorgu("/leansys_kontrol_plani?stok_kodu=like.%s&select=stok_kodu,stok_adi&limit=200"
                       % urllib.parse.quote(kok + "*"))
    except Exception:
        benzer = []
    kodlar = sorted({met(b["stok_kodu"]) for b in benzer} - {v["kod"]})
    v["benzer"] = ("Benzer parça(lar): " + ", ".join(kodlar[:6])) if kodlar else \
                  "ERP'de benzer/karşılaştırılabilir parça bulunmadı — yeni proses"

    # Kapasite: vardiya süresi kapasite_sure'den (LeanSys 31500 sn ≈ 8,75 saat)
    sureler = [round(float(met(r.get("kapasite_sure")) or 0)) for r in v["rota"]]
    v["vardiya_sure"] = max(sureler) if sureler else 480
    # LeanSys bu alani kimi urunde SANIYE (31500), kiminde DAKIKA (480) tutuyor.
    # 1440'in altindaki deger bir vardiyayi saniyeyle anlatamaz -> dakikadir.
    v["birim"] = "dk" if v["vardiya_sure"] <= 1440 else "sn"
    v["vardiya_saat"] = v["vardiya_sure"] / (60.0 if v["birim"] == "dk" else 3600.0)
    satirlar = []
    for r in v["rota"]:
        # LeanSys bu alanlari ondalikli da doldurabiliyor (19090.9 gibi)
        std = float(met(r.get("std_zaman")) or 0)
        kap = round(float(met(r.get("kapasite")) or 0))
        sure = round(float(met(r.get("kapasite_sure")) or 0))
        if std <= 1 and kap <= 1:          # hazırlık/boş satır
            continue
        satirlar.append({
            "op": met(r.get("op_no")), "makine": met(r.get("makine_adi")),
            "std": std, "personel": met(r.get("personel")), "sure": sure,
            "kap": kap, "gunluk": kap * 3, "not": met(r.get("talimat")) or "",
            "darbogaz": False,
        })
    if satirlar:
        db = min(satirlar, key=lambda x: x["kap"])
        db["darbogaz"] = True
        v["darbogaz"] = db
    else:
        v["darbogaz"] = {"makine": "—", "kap": 0, "gunluk": 0}
    v["kapasite_satirlari"] = satirlar
    return v


def main():
    if len(sys.argv) < 2:
        raise SystemExit("kullanım: python apqp_belge_uret.py <stok kodu>")
    kod = sys.argv[1]
    v = zenginlestir(urun_verisi(kod))
    klasor = os.path.join(DRIVE, kod)
    os.makedirs(klasor, exist_ok=True)

    print("%s — %s" % (kod, v["ad"]))
    print("   müşteri: %s | lokasyon: %s | devreye alma: %s"
          % (v["musteri"], v["lokasyon_ad"], v["devreye"]))
    print("   klasör : %s" % klasor)

    p = os.path.join(klasor, "PL74 Proses Akış Diyagramı %s.xlsx" % kod)
    n = pl74(v, p); print("   ✓ PL74 Proses Akış Diyagramı      (%d adım)" % n)

    p = os.path.join(klasor, "FR90 Fizibilite Taahhüdü %s.xlsm" % kod)
    fr90(v, p); print("   ✓ FR90 Fizibilite Taahhüdü         (başlık dolduruldu, cevaplar ekipte)")

    p = os.path.join(klasor, "FR81 Toplantı Tutanağı %s.xlsx" % kod)
    n = fr81(v, p); print("   ✓ FR81 Toplantı Tutanağı           (%d gündem maddesi)" % n)

    p = os.path.join(klasor, "Kapasite Takip Formu %s.xlsx" % kod)
    n = kapasite(v, p); print("   ✓ Kapasite Takip Formu             (%d operasyon, darboğaz: %s / %s adet)"
                              % (n, v["darbogaz"]["makine"][:26], v["darbogaz"]["kap"]))


if __name__ == "__main__":
    main()
