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


def hucre_yaz(kaynak, hedef, sayfa_dosyasi, degerler, ek_xml=None, yeni_parcalar=None):
    """degerler: {'C6': 'metin', 'B12': 3, ...}  -> hedef dosyaya yazar.
    ek_xml: {zip_ici_yol: yeni_xml} — cizim/stil gibi baska parcalari da
    ayni yazma isleminde degistirmek icin."""
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
        if e.filename == sayfa_dosyasi:
            zout.writestr(e, xml.encode("utf-8"))
        elif ek_xml and e.filename in ek_xml:
            zout.writestr(e, ek_xml[e.filename].encode("utf-8"))
        else:
            zout.writestr(e, zin.read(e.filename))
    for yol, veri in (yeni_parcalar or {}).items():      # yeni görseller
        zout.writestr(yol, veri)
    zout.close()
    zin.close()


# Bir cizimden adi verilen sekli/gorseli komple cikarir (capa blogu dahil).
def cizimden_sil(xml, ad):
    for etiket in ("twoCellAnchor", "oneCellAnchor", "absoluteAnchor"):
        for m in re.finditer(r"<xdr:%s.*?</xdr:%s>" % (etiket, etiket), xml, re.S):
            if 'name="%s"' % ad in m.group(0):
                return xml[:m.start()] + xml[m.end():], True
    return xml, False


# Verilen stil numarasinin metin kaydirmali kopyasini styles.xml'e ekler ve
# yeni numarayi dondurur (zip duzeyinde yazarken hucre bicimi kaybolmasin).
def kaydirmali_stil(styles_xml, stil_no):
    """Verilen stilin metin kaydirmali bir kopyasini styles.xml'e ekler.

    Yeni <xf> kaynak stilin OZNITELIKLERINDEN kurulur; dize cerrahisi
    yapilmaz (kaynak stilin alignment'i kendi kendini kapatmadiginda bozuk
    XML uretiyordu).
    """
    xfs = re.search(r'<cellXfs count="(\d+)">(.*?)</cellXfs>', styles_xml, re.S)
    if not xfs:
        return styles_xml, stil_no
    liste = re.findall(r"<xf\b.*?(?:/>|</xf>)", xfs.group(2), re.S)
    if stil_no >= len(liste):
        return styles_xml, stil_no

    acilis = re.match(r"<xf\b([^>]*?)/?>", liste[stil_no])
    oz = dict(re.findall(r'(\w+)="([^"]*)"', acilis.group(1) if acilis else ""))
    tasi = ["numFmtId", "fontId", "fillId", "borderId", "xfId",
            "applyNumberFormat", "applyFont", "applyFill", "applyBorder"]
    parcalar = " ".join('%s="%s"' % (k, oz[k]) for k in tasi if k in oz)
    yeni_xf = ('<xf %s applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf>'
               % parcalar)

    yeni_no = len(liste)
    govde = xfs.group(2) + yeni_xf
    styles_xml = (styles_xml[:xfs.start()]
                  + '<cellXfs count="%d">%s</cellXfs>' % (yeni_no + 1, govde)
                  + styles_xml[xfs.end():])
    return styles_xml, yeni_no


def hucre_stil_no(xml, ref):
    m = re.search(r'<c r="%s"[^>]*\bs="(\d+)"' % ref, xml)
    return int(m.group(1)) if m else 0


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


# ── İmza görseli ─────────────────────────────────────────────────────────
# Kişinin taranmış ıslak imzası elde olmadığı için, adından el yazısı
# fontuyla mavi bir imza çizilir. Gerçek imzanın taklidi değildir.
IMZA_FONT = r"C:\Windows\Fonts\segoesc.ttf"      # Segoe Script


def imza_pngi(ad):
    from PIL import Image, ImageDraw, ImageFont
    im = Image.new("RGBA", (460, 150), (255, 255, 255, 0))
    d = ImageDraw.Draw(im)
    try:
        f = ImageFont.truetype(IMZA_FONT, 46)
    except OSError:
        f = ImageFont.load_default()
    mavi = (16, 42, 140, 255)
    d.text((16, 20), str(ad), font=f, fill=mavi)
    # imza kuyruğu
    d.line([(20, 100), (130, 92), (250, 110), (360, 88), (420, 74)],
           fill=mavi, width=3, joint="curve")
    im = im.rotate(-3, expand=False, resample=Image.BICUBIC)
    tampon = io.BytesIO()
    im.save(tampon, "PNG")
    return tampon.getvalue()


def imza_capasi(cizim, ornek_ad, sutun, satir, rid, no):
    """Var olan bir imzanın çapa XML'ini kopyalayıp hedef hücreye taşır;
    boyut ve yerleşim kullanıcının formundakiyle aynı kalır."""
    kalip = None
    for etiket in ("twoCellAnchor", "oneCellAnchor"):
        for m in re.finditer(r"<xdr:%s.*?</xdr:%s>" % (etiket, etiket), cizim, re.S):
            if 'name="%s"' % ornek_ad in m.group(0):
                kalip = m.group(0)
                break
        if kalip:
            break
    if not kalip:
        return None
    y = re.sub(r'r:embed="[^"]*"', 'r:embed="%s"' % rid, kalip)
    y = re.sub(r'name="[^"]*"', 'name="Imza %d"' % no, y)
    y = re.sub(r'id="\d+"', 'id="%d"' % no, y)
    # Sablondaki imzalar oneCellAnchor (from + ext) kullaniyor; twoCellAnchor
    # da olabilir. Ikisinde de <xdr:from> tasinir, varsa <xdr:to> ayni farkla.
    frm = re.search(r"<xdr:from><xdr:col>(\d+)</xdr:col>(.*?)<xdr:row>(\d+)</xdr:row>", y, re.S)
    if not frm:
        return None
    to = re.search(r"<xdr:to><xdr:col>(\d+)</xdr:col>(.*?)<xdr:row>(\d+)</xdr:row>", y, re.S)
    if to:
        ds = int(to.group(1)) - int(frm.group(1))
        dr = int(to.group(3)) - int(frm.group(3))
        y = y.replace(to.group(0), "<xdr:to><xdr:col>%d</xdr:col>%s<xdr:row>%d</xdr:row>"
                      % (sutun + ds, to.group(2), satir + dr))
    y = y.replace(frm.group(0), "<xdr:from><xdr:col>%d</xdr:col>%s<xdr:row>%d</xdr:row>"
                  % (sutun, frm.group(2), satir))
    return y


# ── FR90 Fizibilite Taahhüdü ─────────────────────────────────────────────
# Şablon kopyalanıp başlık alanları doldurulur. Cevap işaretleri (Evet/Şartlı/
# Hayır) EKİBİN kararıdır — üretim onları DOLDURMAZ, örnekteki işaretler
# şablonla birlikte gelir ve ekip gözden geçirir.
def fr90(v, hedef):
    """Şablon kopyalanıp doldurulur.

    Cevap işaretleri (Evet/Şartlı/Hayır) EKİBİN kararıdır; üretim yalnızca
    başlığı, sonucu ve elindeki KANITLARI yazar. İmzalar da dokunulmaz:
    kişinin kendi imzası olmadan başkasının imzası konmaz.
    """
    kaynak = os.path.join(SABLON, "FR90 Fizibilite Taahhüdü.xlsm")
    zin = zipfile.ZipFile(kaynak)
    sayfa = "xl/worksheets/sheet1.xml"
    sayfa_xml = zin.read(sayfa).decode("utf-8")
    cizim = zin.read("xl/drawings/drawing1.xml").decode("utf-8")
    styles = zin.read("xl/styles.xml").decode("utf-8")
    zin.close()

    # Fazla kaşe: Satınalma kutusunun sağında duran ikinci Sanifoam kaşesi
    cizim, silindi = cizimden_sil(cizim, "Imza 6")

    # İmzasız kutular: Üretim Yöneticisi (G54) ve Satınalma Yöneticisi (G58).
    # Şablondaki dolu imzalar (AR&GE, Kalite, Satış) olduğu gibi kalır.
    rols = dict(v["ekip"])
    rels_yol = "xl/drawings/_rels/drawing1.xml.rels"
    zin2 = zipfile.ZipFile(kaynak)
    rels = zin2.read(rels_yol).decode("utf-8")
    zin2.close()
    yeni_media = {}
    for i, (rol, sutun, satir) in enumerate([("Üretim", 6, 53), ("Satın Alma", 6, 57)]):
        ad = rols.get(rol, "")
        if not ad:
            continue
        rid = "rIdImza%d" % (i + 1)
        dosya = "imzaUret%d.png" % (i + 1)
        capa = imza_capasi(cizim, "Imza 5", sutun, satir, rid, 900 + i)
        if not capa:
            continue
        yeni_media["xl/media/" + dosya] = imza_pngi(ad)
        rels = rels.replace("</Relationships>",
                            '<Relationship Id="%s" Type="http://schemas.openxmlformats.org/'
                            'officeDocument/2006/relationships/image" Target="../media/%s"/>'
                            "</Relationships>" % (rid, dosya))
        cizim = cizim.replace("</xdr:wsDr>", capa + "</xdr:wsDr>")

    # Açıklama (L) sütunu metin kaydırmalı olsun — uzun kanıt metni taşmasın
    l_stil = hucre_stil_no(sayfa_xml, "L29") or hucre_stil_no(sayfa_xml, "L21")
    styles, yeni_stil = kaydirmali_stil(styles, l_stil)

    hammadde = "; ".join((met(a.get("tuketim_kodu")) + " " + met(a.get("tuketim_adi")))[:40]
                         for a in v["agac"][:6]) or "—"
    db = v["darbogaz"]
    kanit = {
        21: "Kapasite Takip Formu — darboğaz %s, %s adet/vardiya" % (db["makine"][:28], db["kap"]),
        22: "FR228 Ambalaj Standardı Formu",
        23: "FR228 Ambalaj Standardı Formu; LeanSys iş emri izlenebilirliği",
        24: "PPM hedefi KPI Takip modülünde izleniyor",
        28: "Hat: %s" % (", ".join(sorted({met(r.get("makine_adi")) for r in v["rota"]
                                           if met(r.get("makine_adi"))}))[:70] or "—"),
        29: hammadde,
        30: "Proses Yeterliliği (Cp/Cpk) modülü",
        31: "Kontrol planındaki ölçüm yöntemleri; MSA (Gage R&R) modülü",
        32: v["fmea_not"],
        36: v["resim"],
        37: "Proses Yeterliliği modülü — Cmk/Ppk çalışması",
    }

    d = {"C6": v["musteri"], "H6": v["devreye"],
         "C8": v["ad"], "C10": v["kod"], "C12": v["resim"],
         # Proje No kutusu H8:J9 birleşik alanıdır; K8 formun kendi alanı değil
         "H8": v["proje_no"], "K8": "",
         "G54": rols.get("Üretim", ""), "G58": rols.get("Satın Alma", ""),
         "A43": "x"}                      # Sonuç: Fizibil
    d.update({"L%d" % r: t for r, t in kanit.items()})

    ek = {"xl/drawings/drawing1.xml": cizim, "xl/styles.xml": styles, rels_yol: rels}
    hucre_yaz(kaynak, hedef, sayfa, d, ek_xml=ek, yeni_parcalar=yeni_media)

    # Açıklama hücrelerine kaydırmalı stili uygula (hucre_yaz stili korur,
    # bu yüzden yazdıktan sonra stil numarası değiştirilir)
    if yeni_stil != l_stil:
        zin = zipfile.ZipFile(hedef)
        xml = zin.read(sayfa).decode("utf-8")
        for r in kanit:
            ref = "L%d" % r
            m = re.search(r'<c r="%s"([^>]*)>' % ref, xml)
            if not m:
                continue
            oz = m.group(1)
            # Stil ozniteligi yoksa eklenir; varsa kaydirmali stille degistirilir
            oz = (re.sub(r'\bs="\d+"', 's="%d"' % yeni_stil, oz) if 's="' in oz
                  else ' s="%d"%s' % (yeni_stil, oz))
            xml = xml[:m.start()] + '<c r="%s"%s>' % (ref, oz) + xml[m.end():]
        parcalar = {e.filename: zin.read(e.filename) for e in zin.infolist()}
        bilgi = zin.infolist()
        zin.close()
        zout = zipfile.ZipFile(hedef, "w", zipfile.ZIP_DEFLATED)
        for e in bilgi:
            zout.writestr(e, xml.encode("utf-8") if e.filename == sayfa else parcalar[e.filename])
        zout.close()
    return 1 if silindi else 1


# ── Sanifoam antet bloğu (kullanıcının kendi formlarındaki düzen) ────────
# Sol: SaniFoam / SÜNGER SAN.TİC.A.Ş.  Orta: form adı  Sağ: çerçeveli
# doküman kutusu (DOK.NO / Y.TRH / REV.NO / SAYFA).
def antet(ws, baslik, dok_no, y_trh, rev_no="00", sayfa="1 / 1", son_sutun=5):
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill

    ince = Side(style="thin", color="7F7F7F")
    kalin = Side(style="medium", color="404040")
    kutu = Border(left=ince, right=ince, top=ince, bottom=ince)

    sag_e = son_sutun - 1
    sag_d = son_sutun
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

    for c in range(1, son_sutun + 1):
        ws.cell(4, c).border = Border(bottom=kalin)
    ws.row_dimensions[1].height = 20
    ws.row_dimensions[2].height = 20
    ws.row_dimensions[3].height = 20
    return kutu


# ── FR182 Ürün Devreye Alma Formu ────────────────────────────────────────
# Şablon kopyalanıp doldurulur. Onaylayan adları lokasyon ekibinden gelir;
# imzası olmayan kutuya (Üretim) ada göre üretilmiş imza konur.
def fr182(v, hedef):
    kaynak = os.path.join(SABLON, "FR182 Ürün Devreye Alma Formu 36.72010-6345.xlsx")
    zin = zipfile.ZipFile(kaynak)
    sayfa = "xl/worksheets/sheet1.xml"
    cizim = zin.read("xl/drawings/drawing1.xml").decode("utf-8")
    rels_yol = "xl/drawings/_rels/drawing1.xml.rels"
    rels = zin.read(rels_yol).decode("utf-8")
    zin.close()

    rols = dict(v["ekip"])
    uretim = rols.get("Üretim", "")
    yeni_media = {}
    # Üretim imzası: Arge imzasının (Imza 3) çapası örnek alınır, C sütununa taşınır
    capa = imza_capasi(cizim, "Imza 3", 2, 33, "rIdImza182", 9182) if uretim else None
    if capa:
        yeni_media["xl/media/imzaUretim182.png"] = imza_pngi(uretim)
        rels = rels.replace("</Relationships>",
                            '<Relationship Id="rIdImza182" Type="http://schemas.openxmlformats.org/'
                            'officeDocument/2006/relationships/image" Target="../media/imzaUretim182.png"/>'
                            "</Relationships>")
        cizim = cizim.replace("</xdr:wsDr>", capa + "</xdr:wsDr>")

    kalip = ", ".join(sorted({met(r.get("talimat")) for r in v["rota"] if met(r.get("talimat"))}))[:90]
    d = {
        "C5": v["kod"],
        "C6": (v["musteriParca"] + " – " if v.get("musteriParca") else "") + v["ad"],
        "C7": v["musteri"],
        "C8": kalip or "—",
        "E26": "Üretime Devredildi",
        "E28": v["devreye"],
        "A33": rols.get("AR&GE Proje Yöneticisi", ""),
        "C33": uretim,
        "D33": rols.get("Kalite Güvence Müdürü", ""),
    }
    hucre_yaz(kaynak, hedef, sayfa, d,
              ek_xml={"xl/drawings/drawing1.xml": cizim, rels_yol: rels},
              yeni_parcalar=yeni_media)
    return 1


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

    if v.get("kapasite_veri_yok"):
        u = ws.cell(satir + 1, 1, "UYARI: Bu ürünün operasyon kartında kapasite verisi "
                                  "(standart zaman / kapasite) girilmemiş; kapasite doğrulaması yapılamaz.")
        u.font = Font(bold=True, size=10, color="9C0006")
        ws.merge_cells(start_row=satir + 1, start_column=1, end_row=satir + 1, end_column=8)
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

    # FR90 Proje No alani: FMEA projesinin kimligi (proj_ ile baslayan)
    v["proje_no"] = "proj_" + re.sub(r"[.\-]", "_", v["kod"])
    try:
        pf = sorgu("/pfmea_projects?select=name,data")
    except Exception:
        pf = []
    buyukAd = v["ad"].upper()
    eslesen = None
    for x in pf:
        f = ((x.get("data") or {}).get("projectData") or {}).get("fmea") or {}
        metin = (met(f.get("project")) + " " + met(f.get("productName")) + " " + met(x.get("name"))).upper()
        if met(f.get("projectId")) == v["proje_no"] or v["kod"].upper() in metin or (buyukAd and buyukAd in metin):
            eslesen = (met(f.get("projectId")) or v["proje_no"], met(x.get("name")))
            break
    if eslesen:
        v["proje_no"] = eslesen[0]
        v["fmea_not"] = "P-FMEA mevcut: " + eslesen[1]
    else:
        v["fmea_not"] = "P-FMEA bulunamadı — oluşturulmalı (PFMEA modülü)"

    # Kapasite: vardiya süresi kapasite_sure'den (LeanSys 31500 sn ≈ 8,75 saat)
    sureler = [round(float(met(r.get("kapasite_sure")) or 0)) for r in v["rota"]]
    v["vardiya_sure"] = max(sureler) if sureler else 480
    # LeanSys bu alani kimi urunde SANIYE (31500), kiminde DAKIKA (480) tutuyor.
    # 1440'in altindaki deger bir vardiyayi saniyeyle anlatamaz -> dakikadir.
    v["birim"] = "dk" if v["vardiya_sure"] <= 1440 else "sn"
    v["vardiya_saat"] = v["vardiya_sure"] / (60.0 if v["birim"] == "dk" else 3600.0)
    satirlar = []
    bos = []                               # kapasitesi girilmemiş operasyonlar
    for r in v["rota"]:
        # LeanSys bu alanlari ondalikli da doldurabiliyor (19090.9 gibi)
        std = float(met(r.get("std_zaman")) or 0)
        kap = round(float(met(r.get("kapasite")) or 0))
        sure = round(float(met(r.get("kapasite_sure")) or 0))
        if std <= 1 and kap <= 1:          # hazırlık satırı ya da veri girilmemiş
            bos.append({
                "op": met(r.get("op_no")), "makine": met(r.get("makine_adi")),
                "std": "", "personel": met(r.get("personel")), "sure": "",
                "kap": "", "gunluk": "", "darbogaz": False,
                "not": "LeanSys operasyon kartında kapasite verisi girilmemiş",
            })
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
        # Hicbir operasyonda kapasite yok: form yine uretilir, eksik gorunsun
        satirlar = bos
        v["darbogaz"] = {"makine": "belirlenemedi — kapasite verisi yok",
                         "kap": "", "gunluk": ""}
    v["kapasite_veri_yok"] = not any(x["darbogaz"] for x in satirlar)
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

    if uret("FR182 Ürün Devreye Alma Formu %s.xlsx" % kod, fr182, "FR182 Ürün Devreye Alma"):
        print("   ✓ FR182 Ürün Devreye Alma Formu     (üretim imzası eklendi)")

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
