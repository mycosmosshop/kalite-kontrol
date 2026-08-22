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


# ── Sanifoam antet blogu (kullanicinin kendi formlarindaki duzen) ────────
# Sol: SaniFoam / SÜNGER SAN.TİC.A.Ş.  Orta: form adi  Sag: cerceveli
# dokuman kutusu (DOK.NO / Y.TRH / REV.NO / SAYFA).
def antet(ws, baslik, dok_no, y_trh, rev_no="00", sayfa="1 / 1", son_sutun=5):
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
    from openpyxl.utils import get_column_letter

    ince = Side(style="thin", color="7F7F7F")
    kalin = Side(style="medium", color="404040")
    kutu = Border(left=ince, right=ince, top=ince, bottom=ince)

    sag_e = son_sutun - 1          # etiket sutunu
    sag_d = son_sutun              # deger sutunu
    orta_son = sag_e - 1

    ws.merge_cells(start_row=1, start_column=1, end_row=3, end_column=1)
    a = ws.cell(1, 1, "SaniFoam")
    a.font = Font(size=20, bold=True, color="1F3864")
    a.alignment = Alignment(horizontal="center", vertical="center")
    ws.cell(4, 1, "SÜNGER SAN.TİC.A.Ş.").font = Font(size=8, color="595959")
    ws.cell(4, 1).alignment = Alignment(horizontal="center")

    ws.merge_cells(start_row=1, start_column=2, end_row=1, end_column=orta_son)
    u = ws.cell(1, 2, "KALİTE YÖNETİM SİSTEMİ DOKÜMANTASYONU")
    u.font = Font(size=9, color="595959"); u.alignment = Alignment(horizontal="center")

    ws.merge_cells(start_row=2, start_column=2, end_row=4, end_column=orta_son)
    b = ws.cell(2, 2, baslik)
    b.font = Font(size=20, bold=True, color="1F3864")
    b.alignment = Alignment(horizontal="center", vertical="center")

    for i, (e, d) in enumerate([("DOK.NO", dok_no), ("Y.TRH", y_trh),
                                ("REV.NO", rev_no), ("SAYFA", sayfa)]):
        ce = ws.cell(1 + i, sag_e, e); cd = ws.cell(1 + i, sag_d, d)
        ce.font = Font(size=9, bold=True); cd.font = Font(size=9)
        ce.alignment = Alignment(horizontal="left", vertical="center")
        cd.alignment = Alignment(horizontal="center", vertical="center")
        ce.fill = PatternFill("solid", fgColor="F2F2F2")
        ce.border = kutu; cd.border = kutu

    for c in range(1, son_sutun + 1):          # antet alt cizgisi
        ws.cell(4, c).border = Border(bottom=kalin)
    ws.row_dimensions[1].height = 20
    ws.row_dimensions[2].height = 20
    ws.row_dimensions[3].height = 20
    return kutu


# ── FR81 Toplantı Tutanağı (şablon yok — Sanifoam antet düzeninde üretilir) ──
# Konular APQP başlangıç toplantısının standart gündemi: altyapı/ekipman,
# tedarikçi, şartname, teknik resim, benzer parça geçmişi, fizibilite.
def fr81(v, hedef):
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill

    wb = Workbook(); ws = wb.active; ws.title = "Toplantı Tutanağı"
    ws.sheet_view.showGridLines = False
    for h, g in zip("ABCDE", (13, 58, 20, 14, 42)):
        ws.column_dimensions[h].width = g

    kutu = antet(ws, "TOPLANTI TUTANAĞI", "FR 81", "01.09.2004", son_sutun=5)

    def alan(satir, etiket, deger, birlestir_son=None):
        c = ws.cell(satir, 1, etiket)
        c.font = Font(bold=True, size=10)
        c.alignment = Alignment(horizontal="right", vertical="center")
        d = ws.cell(satir, 2, deger)
        d.alignment = Alignment(vertical="center", wrap_text=True)
        if birlestir_son:
            ws.merge_cells(start_row=satir, start_column=2, end_row=satir, end_column=birlestir_son)
        return d

    alan(6, "TOPLANTI TARİHİ :", v["devreye_baslangic"])
    ws.cell(6, 3, "TOPLANTI SAATİ :").font = Font(bold=True, size=10)
    ws.cell(6, 3).alignment = Alignment(horizontal="right")
    ws.cell(6, 4, "14:00").alignment = Alignment(horizontal="center")
    alan(7, "KONU :", "%s (%s) — APQP başlangıç / fizibilite değerlendirmesi" % (v["ad"], v["kod"]), 5)
    k = alan(8, "KATILIMCILAR :", ", ".join("%s (%s)" % (ad, rol) for rol, ad in v["ekip"]), 5)
    k.alignment = Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[8].height = 34

    for i, b in enumerate(["NO", "KONU", "SORUMLU", "TERMİN", "AÇIKLAMA"]):
        c = ws.cell(10, 1 + i, b)
        c.font = Font(bold=True, size=11, color="FFFFFF")
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.fill = PatternFill("solid", fgColor="1F3864"); c.border = kutu
    ws.row_dimensions[10].height = 24

    hammadde = ", ".join(met(a.get("tuketim_kodu")) for a in v["agac"][:5]) or "ürün ağacında hammadde yok"
    makineler = ", ".join(sorted({met(r.get("makine_adi")) for r in v["rota"] if met(r.get("makine_adi"))})) or "—"
    rolAd = dict((r, a) for r, a in v["ekip"])
    gundem = [
        ("Müşteri teknik resmi ve şartnamelerin incelenmesi (%s)" % v["resim"],
         rolAd["AR&GE Proje Yöneticisi"], "Teknik resim ve şartname ERP stok dokümanlarında kayıtlı"),
        ("Özel/kritik karakteristiklerin belirlenmesi",
         rolAd["Kalite Güvence Müdürü"], "Kontrol planındaki özel karakteristikler PFMEA'ya aktarılacak"),
        ("Altyapı, ekipman ve tesis yeterliliği değerlendirmesi",
         rolAd["Üretim"], "Kullanılacak hat: %s" % makineler[:150]),
        ("Ölçüm/test ekipmanı ve kalibrasyon ihtiyacı",
         rolAd["Kalite Mühendisi"], "Kontrol planındaki ölçüm yöntemleri için ekipman uygunluğu"),
        ("Hammadde ve alt tedarikçi durumu",
         rolAd["Satın Alma"], "Ürün ağacı: %s — tedarikçiler onaylı tedarikçi listesinden seçilecek" % hammadde[:110]),
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
        r = 11 + i
        for j, deger in enumerate([i + 1, konu, sorumlu, v["termin"], aciklama]):
            c = ws.cell(r, 1 + j, deger)
            c.border = kutu
            c.font = Font(size=10)
            c.alignment = Alignment(wrap_text=True, vertical="center",
                                    horizontal="center" if j in (0, 2, 3) else "left")
            if i % 2:
                c.fill = PatternFill("solid", fgColor="F7F9FC")
        ws.row_dimensions[r].height = 34

    r = 11 + len(gundem) + 1
    ws.cell(r, 1, "Kaynak: ERP ürün ağacı, operasyon kartı, kontrol planı ve stok dokümanları."
            ).font = Font(size=8, italic=True, color="808080")
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5)
    ws.print_area = "A1:E%d" % r
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    wb.save(hedef)
    return len(gundem)


# ── Kapasite Takip Formu (şablon yok — Run@Rate mantığında üretilir) ──────
# Operasyon kartındaki std_zaman / kapasite / kapasite_sure gerçek verisinden
# hesaplanır. Darboğaz = en düşük vardiya kapasitesi olan operasyon.
def kapasite(v, hedef):
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill

    wb = Workbook(); ws = wb.active; ws.title = "Kapasite"
    ws.sheet_view.showGridLines = False
    for h, g in zip("ABCDEFGH", (13, 34, 14, 11, 12, 15, 16, 46)):
        ws.column_dimensions[h].width = g

    kutu = antet(ws, "KAPASİTE TAKİP FORMU", "FR 24-K",
                 datetime.date.today().strftime("%d.%m.%Y"), son_sutun=8)

    bilgi = [("Parça Kodu :", v["kod"]), ("Parça Adı :", v["ad"]),
             ("Müşteri :", v["musteri"]), ("Lokasyon :", v["lokasyon_ad"]),
             ("Vardiya Süresi :", "%s %s  (%.2f saat)" % (v["vardiya_sure"], v["birim"], v["vardiya_saat"]))]
    for i, (e, d) in enumerate(bilgi):
        c = ws.cell(6 + i, 1, e)
        c.font = Font(bold=True, size=10); c.alignment = Alignment(horizontal="right")
        ws.cell(6 + i, 2, d).alignment = Alignment(vertical="center")

    ust = 12
    basliklar = ["Op", "Operasyon / Makine", "Std. Zaman (%s)" % v["birim"], "Personel",
                 "Vardiya (%s)" % v["birim"], "Vardiya Kapasitesi (adet)",
                 "Günlük (3 vardiya)", "Operasyon Talimatı"]
    for i, b in enumerate(basliklar):
        c = ws.cell(ust, 1 + i, b)
        c.font = Font(bold=True, size=10, color="FFFFFF")
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.fill = PatternFill("solid", fgColor="1F3864"); c.border = kutu
    ws.row_dimensions[ust].height = 30

    satir = ust + 1
    for op in v["kapasite_satirlari"]:
        for j, deger in enumerate([op["op"], op["makine"], op["std"], op["personel"],
                                   op["sure"], op["kap"], op["gunluk"], op["not"]]):
            c = ws.cell(satir, 1 + j, deger)
            c.border = kutu; c.font = Font(size=10, bold=op["darbogaz"])
            c.alignment = Alignment(wrap_text=(j in (1, 7)), vertical="center",
                                    horizontal="left" if j in (1, 7) else "center")
            if op["darbogaz"]:
                c.fill = PatternFill("solid", fgColor="FCE4D6")
        ws.row_dimensions[satir].height = 44
        satir += 1

    satir += 1
    for j, deger in enumerate(["DARBOĞAZ", v["darbogaz"]["makine"], "", "", "",
                               v["darbogaz"]["kap"], v["darbogaz"]["gunluk"],
                               "Hattın kapasitesi bu operasyonla sınırlıdır"]):
        c = ws.cell(satir, 1 + j, deger)
        c.border = kutu; c.font = Font(bold=True, size=10, color="9C0006")
        c.fill = PatternFill("solid", fgColor="FFC7CE")
        c.alignment = Alignment(horizontal="left" if j in (1, 7) else "center",
                                vertical="center", wrap_text=(j == 7))
    ws.row_dimensions[satir].height = 26

    ws.cell(satir + 2, 1, "Kaynak: LeanSys operasyon kartı (std_zaman / kapasite / kapasite_sure). "
                          "Vardiya kapasitesi = vardiya süresi ÷ standart zaman."
            ).font = Font(size=8, italic=True, color="808080")
    ws.merge_cells(start_row=satir + 2, start_column=1, end_row=satir + 2, end_column=8)
    ws.print_area = "A1:H%d" % (satir + 2)
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    wb.save(hedef)
    return len(v["kapasite_satirlari"])


# ── PL11 Onaylı Tedarikçi Listesi ────────────────────────────────────────
# Kaynak: onayli_tedarikci tablosu (tedarikçi modülü "Onaylı Listeyi Buluta
# Yaz" ile doldurur). Ürünün LOKASYONUNA göre süzülür — Ankara ve Çerkezköy
# onaylı listeleri farklıdır — ve Tip A (Otomotiv) tedarikçiler alınır.
def pl11(v, hedef):
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill

    try:
        hepsi = sorgu("/onayli_tedarikci?select=*&order=sinif,ad")
    except Exception as e:
        print("   ! PL11 atlandı — onayli_tedarikci okunamadı (%s)" % str(e)[:60])
        print("     onayli_tedarikci.sql çalıştırıldı mı? Tedarikçi modülünde")
        print("     'Onaylı Listeyi Buluta Yaz' bir kez tıklandı mı?")
        return 0

    lok = v["lokasyon_ad"]
    liste = [t for t in hepsi
             if t.get("otomotiv") and lok in (t.get("lokasyon") or [])]
    if not liste:                      # lokasyon işaretlenmemişse otomotiv olanların tümü
        liste = [t for t in hepsi if t.get("otomotiv")]
        kapsam = "tüm lokasyonlar (bu lokasyona işaretli tedarikçi yok)"
    else:
        kapsam = lok

    wb = Workbook(); ws = wb.active; ws.title = "Onaylı Tedarikçi"
    ws.sheet_view.showGridLines = False
    for h, g in zip("ABCDEFGH", (6, 42, 20, 10, 10, 10, 14, 44)):
        ws.column_dimensions[h].width = g

    kutu = antet(ws, "ONAYLI TEDARİKÇİ LİSTESİ", "PL 11",
                 datetime.date.today().strftime("%d.%m.%Y"), son_sutun=8)

    for i, (e, d) in enumerate([("Lokasyon :", kapsam),
                                ("Kapsam :", "Tip A (Otomotiv) tedarikçiler"),
                                ("İlgili Ürün :", "%s (%s)" % (v["ad"], v["kod"]))]):
        c = ws.cell(6 + i, 1, e)
        c.font = Font(bold=True, size=10); c.alignment = Alignment(horizontal="right")
        ws.cell(6 + i, 2, d)

    ust = 10
    for i, b in enumerate(["Sıra", "Tedarikçi", "Lokasyon", "Sınıf", "Puan",
                           "PPM", "IATF / ISO", "Not"]):
        c = ws.cell(ust, 1 + i, b)
        c.font = Font(bold=True, size=10, color="FFFFFF")
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.fill = PatternFill("solid", fgColor="1F3864"); c.border = kutu
    ws.row_dimensions[ust].height = 24

    renk = {"A": "E2EFDA", "B": "FFF2CC", "C": "FCE4D6", "D": "F2DCDB"}
    for i, t in enumerate(liste):
        r = ust + 1 + i
        belge = " / ".join(x for x in [("IATF" if t.get("iatf") else ""),
                                       ("ISO 9001" if t.get("iso9001") else "")] if x) or "—"
        satir = [i + 1, met(t.get("ad")), ", ".join(t.get("lokasyon") or []),
                 met(t.get("sinif")), t.get("puan"), t.get("ppm"), belge,
                 met(t.get("tavan_not"))]
        for j, deger in enumerate(satir):
            c = ws.cell(r, 1 + j, deger)
            c.border = kutu; c.font = Font(size=10)
            c.alignment = Alignment(wrap_text=(j in (1, 7)), vertical="center",
                                    horizontal="left" if j in (1, 7) else "center")
            if j == 3 and met(t.get("sinif")) in renk:
                c.fill = PatternFill("solid", fgColor=renk[met(t.get("sinif"))])
        ws.row_dimensions[r].height = 20

    son = ust + len(liste) + 2
    ws.cell(son, 1, "Kaynak: ERP Onaylı Tedarikçi Değerlendirme modülü — "
                    "otomotiv (Tip A) filtresi, %s lokasyonu. Sınıf tavanı uygulanan "
                    "tedarikçilerde gerekçe Not sütunundadır." % kapsam
            ).font = Font(size=8, italic=True, color="808080")
    ws.merge_cells(start_row=son, start_column=1, end_row=son, end_column=8)
    ws.print_area = "A1:H%d" % son
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    wb.save(hedef)
    return len(liste)


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

    def uret(dosya, islev, etiket):
        """Belgeyi gecici ada yazip yerine koyar. Dosya Excel'de acikken
        (Permission denied) tum uretim durmasin diye tek tek yakalanir."""
        yol = os.path.join(klasor, dosya)
        gecici = yol + ".yeni"
        try:
            sonuc = islev(v, gecici)
            if not sonuc or not os.path.exists(gecici):
                # Uretilmedi (or. PL11 kaynagi yok) - bos dosya birakma
                if os.path.exists(gecici): os.remove(gecici)
                return None
            os.replace(gecici, yol)
            return sonuc
        except PermissionError:
            try: os.remove(gecici)
            except OSError: pass
            print("   ! %-32s dosya açık, yazılamadı — Excel'de kapatıp tekrar çalıştırın" % etiket)
            return None
        except Exception as e:
            try: os.remove(gecici)
            except OSError: pass
            print("   ! %-32s üretilemedi: %s" % (etiket, str(e)[:70]))
            return None

    n = uret("PL74 Proses Akış Diyagramı %s.xlsx" % kod, pl74, "PL74 Proses Akış Diyagramı")
    if n: print("   ✓ PL74 Proses Akış Diyagramı      (%d adım)" % n)

    if uret("FR90 Fizibilite Taahhüdü %s.xlsm" % kod, lambda a, b: (fr90(a, b), 1)[1],
            "FR90 Fizibilite Taahhüdü"):
        print("   ✓ FR90 Fizibilite Taahhüdü         (başlık dolduruldu, cevaplar ekipte)")

    n = uret("FR81 Toplantı Tutanağı %s.xlsx" % kod, fr81, "FR81 Toplantı Tutanağı")
    if n: print("   ✓ FR81 Toplantı Tutanağı           (%d gündem maddesi)" % n)

    n = uret("PL11 Onaylı Tedarikçi Listesi %s.xlsx" % kod, pl11, "PL11 Onaylı Tedarikçi Listesi")
    if n:
        print("   ✓ PL11 Onaylı Tedarikçi Listesi     (%d otomotiv tedarikçi, %s)" % (n, v["lokasyon_ad"]))

    n = uret("Kapasite Takip Formu %s.xlsx" % kod, kapasite, "Kapasite Takip Formu")
    if n: print("   ✓ Kapasite Takip Formu             (%d operasyon, darboğaz: %s / %s adet)"
                % (n, v["darbogaz"]["makine"][:26], v["darbogaz"]["kap"]))


if __name__ == "__main__":
    main()
