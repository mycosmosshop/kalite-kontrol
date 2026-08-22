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


# ── FR81 Toplantı Tutanağı ───────────────────────────────────────────────
# Bir ürün kodunun tutanağı TEKTİR ve büyüyerek devam eder: her toplantıda
# APQP madde numarasına göre yeni maddeler ALTINA eklenir, var olanların
# durumu/açıklaması olduğu gibi kalır. Gündem, FR91 listesinde tutanağa
# bağlanan APQP maddelerinden gelir.
FR81_SUTUN = ["NO", "APQP MADDE", "KONU", "SORUMLU", "TERMİN", "AÇIKLAMA", "DURUM"]


def fr81_gundem(v):
    """APQP maddesi -> (konu, rol, açıklama). FR91'de FR81'e bağlanan maddeler."""
    hammadde = ", ".join(met(a.get("tuketim_kodu")) for a in v["agac"][:5]) or "ürün ağacında hammadde yok"
    makineler = ", ".join(sorted({met(r.get("makine_adi")) for r in v["rota"]
                                  if met(r.get("makine_adi"))})) or "—"
    aletler = ", ".join(sorted({g["alet"] for g in msa_aletleri(v["kod"])})) or "—"
    return [
        ("2.1", "Benzer/karşılaştırılabilir parça geçmişi incelendi",
         "AR&GE Proje Yöneticisi", v["benzer"]),
        ("2.2", "Özel/kritik karakteristikler belirlendi",
         "Kalite Güvence Müdürü", "Kontrol planındaki özel karakteristikler PFMEA'ya aktarılacak"),
        ("2.4", "Yeni alet, ekipman ve tesis gereksinimleri — altyapı yeterliliği",
         "Üretim", "Kullanılacak hat: %s" % makineler[:150]),
        ("2.5", "Yeni gösterge, fikstür ve test ekipmanı gereksinimleri",
         "Kalite Mühendisi", "Kontrol planındaki ölçüm aletleri: %s" % aletler[:150]),
        ("2.6", "İlk kapasite değerlendirmesi",
         "Üretim", "Darboğaz operasyon ve vardiya kapasitesi Kapasite Takip Formunda"),
        ("2.7", "Hammadde ve alt tedarikçi durumu",
         "Satın Alma", "Ürün ağacı: %s — tedarikçiler PL11 onaylı listeden seçilecek" % hammadde[:110]),
        ("2.8", "Müşteri teknik resmi ve şartnamelerinin incelenmesi (%s)" % v["resim"],
         "AR&GE Proje Yöneticisi", "Teknik resim ve şartname ERP stok dokümanlarında kayıtlı"),
        ("2.9", "Fizibilite kararı",
         "Kalite Güvence Müdürü", "FR90 Fizibilite Taahhüdü ekip tarafından imzalanacak"),
        ("2.10", "Paketleme planı ve ambalaj standardı",
         "Lojistik", "FR228 Ambalaj Standardı Formu hazırlanacak"),
        ("2.11", "Proje kapsamı ve APQP ekibi tanımlandı (roller, yetkiler, toplantı düzeni)",
         "AR&GE Proje Yöneticisi", "Ekip: " + ", ".join(ad for _, ad in v["ekip"])),
        ("2.13", "Açık konu (concern) matrisi — sorumlu ve termin atandı",
         "Kalite Güvence Müdürü", "Açık konular FR91 takip formundan izlenir"),
        ("2.14", "Risk değerlendirme ve azaltma planı",
         "Kalite Mühendisi", "Riskler PFMEA AP değerleri ve FR148 ile izlenir"),
        ("2.15", "Değişiklik yönetimi başlatıldı",
         "Kalite Güvence Müdürü", "Değişiklik talebi/onayı FR148, revizyon tarihçesi her çıktıda"),
        ("2.16", "APQP program metrikleri yönetime sunuldu",
         "AR&GE Proje Yöneticisi", "Kırmızı/sarı/yeşil durum ve kapı onayı"),
        ("3.4", "Ölçüm sistemi analizi (MSA) planı gözden geçirildi",
         "Kalite Mühendisi", "Kontrol planındaki aletler için MSA Planı ve FR86 formları hazırlandı"),
        ("3.13", "Ürün/proses kalite sistemi gözden geçirmesi",
         "Kalite Güvence Müdürü", "Kontrol planı, PFMEA ve operasyon talimatları uyumu kontrol edildi"),
    ]


def fr81_mevcut(hedef):
    """Var olan tutanaktaki maddeler — yeniden üretimde korunur."""
    if not os.path.exists(hedef):
        return [], 0
    try:
        from openpyxl import load_workbook
        ws = load_workbook(hedef, data_only=True).active
    except Exception:
        return [], 0
    satirlar, enson = [], 0
    for r in ws.iter_rows(min_row=1, max_row=ws.max_row, max_col=len(FR81_SUTUN), values_only=True):
        if r[0] == "NO" or all(x in (None, "") for x in r):
            continue
        try:
            no = int(r[0])
        except (TypeError, ValueError):
            # Toplanti ayirac satiri — oldugu gibi tasinir
            if met(r[0]).startswith("──"):
                satirlar.append(("--", met(r[0]), "", "", "", "", ""))
            continue
        enson = max(enson, no)
        satirlar.append((no,) + tuple(met(x) for x in r[1:7]))
    return satirlar, enson


def fr81(v, hedef):
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill

    eski, enson = fr81_mevcut(hedef)
    varolan = {x[1] for x in eski if x[0] != "--"}      # APQP madde no'lari
    rolAd = dict((rol, ad) for rol, ad in v["ekip"])
    yeni = [(m, k, rolAd.get(rol, rol), a) for m, k, rol, a in fr81_gundem(v) if m not in varolan]

    wb = Workbook(); ws = wb.active; ws.title = "Toplantı Tutanağı"
    ws.sheet_view.showGridLines = False
    for h, g in zip("ABCDEFG", (7, 12, 54, 20, 13, 44, 14)):
        ws.column_dimensions[h].width = g
    kutu = antet(ws, "TOPLANTI TUTANAĞI", "FR 81", "01.09.2004", son_sutun=7)

    def alan(satir, etiket, deger, birlestir_son=None):
        c = ws.cell(satir, 1, etiket)
        c.font = Font(bold=True, size=10)
        c.alignment = Alignment(horizontal="right", vertical="center")
        d = ws.cell(satir, 2, deger)
        d.alignment = Alignment(vertical="center", wrap_text=True)
        if birlestir_son:
            ws.merge_cells(start_row=satir, start_column=2, end_row=satir, end_column=birlestir_son)
        return d

    bugun = datetime.date.today().isoformat()
    toplanti_no = sum(1 for x in eski if x[0] == "--") + 1
    alan(6, "TOPLANTI TARİHİ :", v["devreye_baslangic"] if not eski else bugun)
    ws.cell(6, 4, "TOPLANTI SAATİ :").font = Font(bold=True, size=10)
    ws.cell(6, 4).alignment = Alignment(horizontal="right")
    ws.cell(6, 5, "14:00").alignment = Alignment(horizontal="center")
    alan(7, "KONU :", "%s (%s) — APQP proje takip toplantıları (%d. toplantı)"
         % (v["ad"], v["kod"], toplanti_no), 7)
    k = alan(8, "KATILIMCILAR :", ", ".join("%s (%s)" % (ad, rol) for rol, ad in v["ekip"]), 7)
    k.alignment = Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[8].height = 34

    for i, b in enumerate(FR81_SUTUN):
        c = ws.cell(10, 1 + i, b)
        c.font = Font(bold=True, size=11, color="FFFFFF")
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.fill = PatternFill("solid", fgColor="1F3864"); c.border = kutu
    ws.row_dimensions[10].height = 24

    def satir_yaz(r, deger, zebra, ayirac=False):
        if ayirac:
            c = ws.cell(r, 1, deger)
            c.font = Font(bold=True, size=9, color="1F3864")
            c.alignment = Alignment(horizontal="left", vertical="center")
            c.fill = PatternFill("solid", fgColor="DCE6F1")
            for j in range(1, len(FR81_SUTUN) + 1):
                ws.cell(r, j).border = kutu
                ws.cell(r, j).fill = PatternFill("solid", fgColor="DCE6F1")
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=len(FR81_SUTUN))
            return
        for j, x in enumerate(deger):
            c = ws.cell(r, 1 + j, x)
            c.border = kutu
            c.font = Font(size=10)
            c.alignment = Alignment(wrap_text=True, vertical="center",
                                    horizontal="center" if j in (0, 1, 3, 4, 6) else "left")
            if zebra:
                c.fill = PatternFill("solid", fgColor="F7F9FC")
        ws.row_dimensions[r].height = 32

    r, z = 11, False
    for x in eski:                                  # onceki toplantilar oldugu gibi
        if x[0] == "--":
            satir_yaz(r, x[1], False, ayirac=True)
        else:
            satir_yaz(r, x, z); z = not z
        r += 1
    if yeni:
        if eski:
            satir_yaz(r, "──  %d. Toplantı — %s  ──" % (toplanti_no, bugun), False, ayirac=True)
            r += 1
        for i, (madde, konu, sorumlu, aciklama) in enumerate(yeni):
            satir_yaz(r, (enson + 1 + i, madde, konu, sorumlu, v["termin"], aciklama, "Açık"), z)
            z = not z
            r += 1

    ws.cell(r + 1, 1, "Maddeler APQP takip formundaki (FR91) madde numaralarına bağlıdır. "
                      "Her toplantıda yeni maddeler bu formun altına eklenir; önceki maddeler korunur."
            ).font = Font(size=8, italic=True, color="808080")
    ws.merge_cells(start_row=r + 1, start_column=1, end_row=r + 1, end_column=7)
    ws.print_area = "A1:G%d" % (r + 1)
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    wb.save(hedef)
    return len(yeni) if yeni else len([x for x in eski if x[0] != "--"])


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
# Format, ERP Onaylı Tedarikçi modülünün KENDİ Excel çıktısıdır (41 sütun,
# başlık bloğu, formüller) — uydurma bir düzen kullanılmaz. Downloads'taki en
# güncel dışa aktarım şablon alınır; ürünün LOKASYONUNA ait olmayan ve
# Tip A (Otomotiv) olmayan satırlar silinir.
# Satır silmeyi EXCEL yapar: dosyada 160 formül, 14 veri doğrulama ve 6 koşullu
# biçim var, Excel bunların aralıklarını kendiliğinden düzeltir.
INDIRILENLER = r"C:\Users\User\Downloads"


def onayli_liste_sablonu():
    """Downloads klasöründeki EN GÜNCEL Onaylı Tedarikçi dışa aktarımı."""
    try:
        adaylar = [os.path.join(INDIRILENLER, f) for f in os.listdir(INDIRILENLER)
                   if f.lower().startswith("onayli_tedarikciler") and f.lower().endswith(".xlsx")]
    except OSError:
        return None
    return max(adaylar, key=os.path.getmtime) if adaylar else None


def pl11(v, hedef):
    import shutil, subprocess, json as _json
    kaynak = onayli_liste_sablonu()
    if not kaynak:
        print("   ! PL11 atlandı — Downloads'ta Onaylı Tedarikçi dışa aktarımı yok;")
        print("     tedarikçi modülünden listeyi bir kez Excel'e aktarın")
        return 0
    shutil.copy2(kaynak, hedef)

    betik = (
        "$ErrorActionPreference='Stop'\n"
        "$f = '" + hedef.replace("'", "''") + "'\n"
        "$lok = '" + v["lokasyon_ad"] + "'\n"
        "$x = New-Object -ComObject Excel.Application\n"
        "$x.Visible = $false; $x.DisplayAlerts = $false\n"
        "try {\n"
        "  $wb = $x.Workbooks.Open($f)\n"
        "  $ws = $wb.Worksheets.Item(1)\n"
        "  $son = $ws.UsedRange.Rows.Count\n"
        "  $silinen = 0; $kalan = 0\n"
        "  for ($r = $son; $r -ge 10; $r--) {\n"
        "    $ad = $ws.Cells.Item($r, 3).Text\n"
        "    if ([string]::IsNullOrWhiteSpace($ad)) { continue }\n"
        "    $l = $ws.Cells.Item($r, 4).Text\n"
        "    $oto = $ws.Cells.Item($r, 40).Text\n"
        "    if (($l -notlike ('*' + $lok + '*')) -or ($oto -ne 'EVET')) {\n"
        "      $ws.Rows.Item($r).Delete() | Out-Null; $silinen++\n"
        "    } else { $kalan++ }\n"
        "  }\n"
        "  $ws.Cells.Item(6, 1).Value2 = 'Lokasyon: " + v["lokasyon_ad"]
        + "   |   Kapsam: Tip A (Otomotiv)   |   Ilgili urun: "
        + (v["kod"] + " - " + v["ad"])[:52].replace("'", " ") + "'\n"
        "  $wb.Save(); $wb.Close($false)\n"
        "  Write-Output ('{\"kalan\":' + $kalan + '}')\n"
        "} finally { $x.Quit(); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($x) }\n")

    try:
        c = subprocess.run(["powershell", "-NoProfile", "-Command", betik],
                           capture_output=True, text=True, timeout=300)
        satir = [x for x in c.stdout.splitlines() if x.strip().startswith("{")]
        if satir:
            return _json.loads(satir[-1]).get("kalan", 0) or 1
        print("   ! PL11 süzülemedi (liste doğru formatta ama süzülmemiş):",
              (c.stderr or c.stdout).strip()[:90].replace("\n", " "))
        return 1
    except Exception as e:
        print("   ! PL11 süzülemedi:", str(e)[:80])
        return 1


# ── FR228 Ambalaj Standardı Formu (docx) ─────────────────────────────────
# Şablon kopyalanır, tablodaki ürün/müşteri alanları güncellenir. Yeni ürün
# için ambalaj FOTOĞRAFI yoktur; şablondaki görseller kaldırılır, yerine
# "fotoğraf eklenecek" notu yazılır (uydurma görsel konmaz).
FR228_SABLON = "FR228 Ambalaj Standartı Formu.docx"


def fr228(v, hedef):
    import docx
    kaynak = os.path.join(SABLON, FR228_SABLON)
    d = docx.Document(kaynak)
    if not d.tables:
        return 0
    t = d.tables[0]
    rols = dict(v["ekip"])

    def yaz(satir, sutun, deger):
        try:
            h = t.cell(satir, sutun)
        except IndexError:
            return
        if h.paragraphs and h.paragraphs[0].runs:
            h.paragraphs[0].runs[0].text = str(deger)
            for r in h.paragraphs[0].runs[1:]:
                r.text = ""
        else:
            h.text = str(deger)

    # Şablondaki hücreleri metinlerinden bul (satır/sütun sabit varsayılmaz)
    for r in range(len(t.rows)):
        for c in range(len(t.columns)):
            try:
                metin = t.cell(r, c).text.strip()
            except IndexError:
                continue
            if metin.startswith("Parça Adı"):
                yaz(r, c + 1, v["ad"])
            elif metin.startswith("Müşteri Adı"):
                yaz(r, c + 1, v["musteri"])
            elif metin.startswith("Parça No"):
                mp = met(v.get("musteriParca")) or met(v.get("ad"))
                yaz(r, c + 1, (mp + " / " if mp and mp != v["kod"] else "") + v["kod"])
            elif metin.startswith("Proje Adı"):
                yaz(r, c + 1, "APQP " + v["kod"])
            elif metin.startswith("Proje Sorumlusu"):
                yaz(r, c + 1, rols.get("Üretim", ""))
            elif metin in ("PROJE",):
                yaz(r + 1, c, rols.get("AR&GE Proje Yöneticisi", ""))
            elif metin in ("KALİTE", "KALITE"):
                yaz(r + 1, c, rols.get("Kalite Güvence Müdürü", ""))
            elif metin in ("ÜRETİM", "URETIM"):
                yaz(r + 1, c, rols.get("Üretim", ""))

    # Şablondaki ambalaj fotoğraflarını kaldır: bu ürüne ait değiller
    # DİKKAT: yalnız <wp:inline> silinirse geride BOŞ <w:drawing> kalır ve Word
    # dosyayı AÇAMAZ. Görseli taşıyan RUN (<w:r>) komple kaldırılır.
    silinen = 0
    for sekil in list(d.inline_shapes):
        try:
            calisma = sekil._inline.getparent().getparent()      # wp:inline > w:drawing > w:r
            calisma.getparent().remove(calisma)
            silinen += 1
        except Exception:
            pass
    if silinen:
        d.add_paragraph("NOT: Ambalaj fotoğrafları bu ürün için henüz çekilmemiştir; "
                        "paketleme yapıldıktan sonra eklenecektir.")
    d.save(hedef)
    return 1


# ── FR148 Değişiklik Yönetimi Formu ──────────────────────────────────────
# AIAG APQP 3rd Ed. 1.15 (değişiklik yönetimi) ve 1.17 (risk değerlendirme)
# bu formla karşılanıyor. Üretim yalnız başlığı ve ilk kaydı doldurur;
# risk satırlarını ekip doldurur.
FR148_SABLON = r"C:\Users\User\Desktop\IATF 16949 URS Denetim 14.08.2026 Ankara\FR148 Değişiklik Yönetimi Formu-TA.2022025-IZOLASYON.xlsx"


def fr148(v, hedef):
    if not os.path.exists(FR148_SABLON):
        return 0
    rols = dict(v["ekip"])
    d = {
        "B11": "APQP %s — %s" % (v["kod"], v["ad"]),
        "B13": rols.get("AR&GE Proje Yöneticisi", ""),
        "B14": v["devreye_baslangic"],
        "B24": rols.get("Kalite Güvence Müdürü", ""),
    }
    hucre_yaz(FR148_SABLON, hedef, "xl/worksheets/sheet1.xml", d)
    return 1


# ── FR181 Öğrenilmiş Dersler ─────────────────────────────────────────────
# Kayıt defteri ortaktır; ürünün KENDİ proseslerine/makinelerine değen
# satırlar işaretlenerek kopyalanır (AIAG 5.4 "read across").
FR181_SABLON = r"C:\Users\User\Desktop\IATF 16949 URS Denetim 14.08.2026 Ankara\FR181 Öğrenilmiş Dersler Lessons Learned.xlsx"


def fr181(v, hedef):
    if not os.path.exists(FR181_SABLON):
        return 0
    import openpyxl
    from openpyxl.styles import PatternFill, Font
    wb = openpyxl.load_workbook(FR181_SABLON)
    ws = wb[wb.sheetnames[0]]
    makineler = {met(r.get("makine_adi")).upper() for r in v["rota"] if met(r.get("makine_adi"))}
    anahtar = set()
    for m in makineler:
        anahtar.update(x for x in re.split(r"[^A-ZÇĞİÖŞÜ0-9]+", m) if len(x) > 3)

    ilgili = 0
    sari = PatternFill("solid", fgColor="FFF2CC")
    for r in range(8, ws.max_row + 1):
        proses = met(ws.cell(r, 5).value).upper()
        makine = met(ws.cell(r, 6).value).upper()
        if not proses and not makine:
            continue
        if any(a in proses or a in makine for a in anahtar):
            ilgili += 1
            for c in range(1, 11):
                ws.cell(r, c).fill = sari
    ws.cell(6, 1, "Gözden Geçirme Tarihi : %s   |   %s (%s) için ilgili kayıtlar sarı işaretli (%d kayıt)"
            % (datetime.date.today().strftime("%d.%m.%Y"), v["kod"], v["ad"][:30], ilgili)).font = Font(bold=True)
    wb.save(hedef)
    return ilgili or 1


# ── FR91 APQP Takip Formu (ürün başlığıyla) ──────────────────────────────
FR91_SABLON = "FR91 APQP-Takip Formu (AIAG 3rd Ed) ŞABLON.xlsx"


def fr91(v, hedef):
    kaynak = os.path.join(SABLON, FR91_SABLON)
    if not os.path.exists(kaynak):
        kaynak = os.path.join(SABLON, "FR91 APQP-Takip Formu 36.72010-6345.xlsx")
    rols = dict(v["ekip"])
    d = {"I6": (v.get("musteriParca") or v["ad"]) + " / " + v["kod"],
         "F8": v["musteri"], "I10": v["devreye_baslangic"]}
    # Ekip satırları (şablonda 14–20)
    for i, (rol, ad) in enumerate(v["ekip"][:7]):
        d["L%d" % (14 + i)] = ad
    hucre_yaz(kaynak, hedef, "xl/worksheets/sheet1.xml", d)
    return 1


# ── APQP Program Metrikleri (şablon yok — AIAG 1.16) ─────────────────────
# Bölüm bazlı kırmızı/sarı/yeşil durum. AIAG: "metrikler programın dürüst
# durumunu yansıtmalı; kırmızı = başlamadı/gecikti, sarı = sürüyor,
# yeşil = tamam."
def program_metrikleri(v, hedef):
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill

    wb = Workbook(); ws = wb.active; ws.title = "Program Metrikleri"
    ws.sheet_view.showGridLines = False
    for h, g in zip("ABCDEF", (10, 52, 14, 14, 14, 30)):
        ws.column_dimensions[h].width = g
    kutu = antet(ws, "APQP PROGRAM METRİKLERİ", "FR91-M",
                 datetime.date.today().strftime("%d.%m.%Y"), son_sutun=6)

    for i, (e, dg) in enumerate([("Parça Kodu :", v["kod"]), ("Parça Adı :", v["ad"]),
                                 ("Müşteri :", v["musteri"]), ("Lokasyon :", v["lokasyon_ad"]),
                                 ("Devreye Alma :", v["devreye"])]):
        c = ws.cell(6 + i, 1, e); c.font = Font(bold=True, size=10)
        c.alignment = Alignment(horizontal="right")
        ws.cell(6 + i, 2, dg)

    ust = 12
    for i, b in enumerate(["Bölüm", "Faz", "Adım", "Tamamlanan", "Durum", "Açıklama"]):
        c = ws.cell(ust, 1 + i, b)
        c.font = Font(bold=True, size=10, color="FFFFFF")
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.fill = PatternFill("solid", fgColor="1F3864"); c.border = kutu
    renk = {"Yeşil": "C6EFCE", "Sarı": "FFEB9C", "Kırmızı": "FFC7CE"}
    yazi = {"Yeşil": "006100", "Sarı": "9C6500", "Kırmızı": "9C0006"}

    satir = ust + 1
    for b in v["apqp_bolumler"]:
        toplam, tamam = b["adim"], b["tamam"]
        durum = "Yeşil" if toplam and tamam == toplam else ("Sarı" if tamam else "Kırmızı")
        aciklama = {"Yeşil": "Tamamlandı", "Sarı": "Sürüyor",
                    "Kırmızı": "Başlamadı / kanıt yok"}[durum]
        for j, deger in enumerate([b["no"], b["ad"], toplam, tamam, durum, aciklama]):
            c = ws.cell(satir, 1 + j, deger)
            c.border = kutu; c.font = Font(size=10, bold=(j == 4), color=yazi[durum] if j == 4 else "000000")
            c.alignment = Alignment(wrap_text=(j in (1, 5)), vertical="center",
                                    horizontal="left" if j in (1, 5) else "center")
            if j == 4:
                c.fill = PatternFill("solid", fgColor=renk[durum])
        ws.row_dimensions[satir].height = 22
        satir += 1

    ws.cell(satir + 1, 1, "AIAG APQP 3rd Ed. 1.16 — metrikler programın dürüst durumunu yansıtmalıdır. "
                          "Kırmızı: başlamadı veya hedef kaçtı · Sarı: sürüyor · Yeşil: tamamlandı."
            ).font = Font(size=8, italic=True, color="808080")
    ws.merge_cells(start_row=satir + 1, start_column=1, end_row=satir + 1, end_column=6)
    ws.page_setup.orientation = "landscape"
    wb.save(hedef)
    return len(v["apqp_bolumler"])


# ── PPAP belgeleri (müşteri bazlı) ───────────────────────────────────────
PPAP_KLASOR = r"C:\\Users\\User\\Desktop\\ppap docs"

# Müşteri anahtar kelimesi -> o müşteriye ait şablonlar
MUSTERI_BELGE = {
    "MERCEDES": ["Cover Sheet Mercedes.doc"],
    "VW":       ["Flammability Test Report VW.xlsx", "Sanifoam_D_TLD_audit_VW.xlsm"],
    "VOLKSWAGEN": ["Flammability Test Report VW.xlsx", "Sanifoam_D_TLD_audit_VW.xlsm"],
    "MAN":      ["VDA_2_2020_Anlagen_Attachments_2-6_7 MAN.xlsx"],
}
# Müşteriye özel kapak/ölçü/parça geçmişi yoksa bu şablon kullanılır
ORTAK_VDA2 = "VDA_2_2020_Anlagen_Attachments_2-6_7 MAN.xlsx"
# Her müşteride ortak belgeler
ORTAK_BELGE = ["Parts History.xlsx", "ISO 845 Density&Weight Test Report.xlsx"]

# Ölçüsel rapor kullanıcının vereceği formatla yapılacak; şimdilik üretilmiyor
URETILMEYEN = ("Dimension Report", "Ölçü Kontrol Raporu")


def musteri_belgeleri(musteri):
    """Müşteriye ait şablon listesi + ortak belgeler. Müşteriye özel kapak
    yoksa VDA_2 şablonu eklenir (kullanıcının kuralı)."""
    m = met(musteri).upper()
    ozel = []
    for anahtar, dosyalar in MUSTERI_BELGE.items():
        if anahtar in m:
            ozel += dosyalar
    kapak_var = any("Cover Sheet" in d or "VDA_2" in d for d in ozel)
    if not kapak_var:
        ozel.append(ORTAK_VDA2)
    return [d for d in dict.fromkeys(ozel + ORTAK_BELGE)
            if not any(u in d for u in URETILMEYEN)]


def parts_history(v, hedef):
    """Parts History: ürün bilgisi doldurulur, değişiklik satırları ekipte."""
    kaynak = os.path.join(PPAP_KLASOR, "Parts History.xlsx")
    if not os.path.exists(kaynak):
        return 0
    d = {"B6": "Designation:  " + v["ad"],
         "B8": "Part no.: " + (v.get("musteriParca") or v["kod"]),
         "B10": "Assembl no.: " + v["kod"]}
    hucre_yaz(kaynak, hedef, "xl/worksheets/sheet1.xml", d)
    return 1


def vda2(v, hedef):
    """VDA_2 Anlagen: PPA Agreement sayfasındaki kuruluş/ürün bilgileri."""
    kaynak = os.path.join(PPAP_KLASOR, ORTAK_VDA2)
    if not os.path.exists(kaynak):
        return 0
    rols = dict(v["ekip"])
    d = {"B5": "Sanifoam Endüstri ve Tüketim Ürünleri San. Tic. A.Ş.",
         "B6": v["lokasyon_ad"],
         "B11": "PPAP " + v["kod"],
         "B12": "1",
         "H23": rols.get("Kalite Güvence Müdürü", ""),
         "H25": rols.get("AR&GE Proje Yöneticisi", "")}
    hucre_yaz(kaynak, hedef, "xl/worksheets/sheet1.xml", d)
    return 1


def ppap_belgeleri(v, klasor, uret):
    """Müşterinin formatındaki PPAP belgelerini ürün klasörüne getirir."""
    import shutil
    sayac = 0
    for dosya in musteri_belgeleri(v["musteri"]):
        kaynak = os.path.join(PPAP_KLASOR, dosya)
        if not os.path.exists(kaynak):
            print("   ! %-34s şablon bulunamadı" % dosya[:34])
            continue
        kok, uzanti = os.path.splitext(dosya)
        hedef_ad = "%s %s%s" % (kok, v["kod"], uzanti)
        hedef = os.path.join(klasor, hedef_ad)
        # Doldurulabilenler doldurulur; eski biçimler (.doc/.xls) kopyalanır
        if dosya == "Parts History.xlsx":
            if uret(hedef_ad, parts_history, "Parts History"):
                print("   ✓ Parts History                     (ürün bilgisi dolduruldu)")
                sayac += 1
            continue
        if dosya == ORTAK_VDA2:
            if uret(hedef_ad, vda2, "VDA_2 Anlagen"):
                print("   ✓ VDA_2 Anlagen (kapak/ölçü/geçmiş)  (kuruluş bilgisi dolduruldu)")
                sayac += 1
            continue
        try:
            shutil.copy2(kaynak, hedef)
            not_ = " — eski biçim, elle doldurulacak" if uzanti.lower() in (".doc", ".xls") else ""
            print("   ✓ %-33s (müşteri formatı%s)" % (kok[:33], not_))
            sayac += 1
        except PermissionError:
            print("   ! %-33s dosya açık, kopyalanamadı" % kok[:33])
    return sayac


# ── PL41 Kontrol Planı (Kalite Kontrol modülünün kendi Excel düzeni) ─────
# Sütunlar/antet kalite_kontrol.html içindeki exportPlanExcel ile birebir aynı:
# 4 satır üst bant + 4 satır meta ızgara + 1 boşluk + başlık + veri.
KP_BASLIK = ["Ölçü No", "Op Kartı", "Op No", "Proses", "Giriş", "Son", "Ölçülecek Değer",
             "Nicel Hedef", "Nitel Hedef / Birim", "Alt Limit", "Üst Limit", "Örn. Büyüklüğü",
             "Örn. Sıklığı", "Son K. Örn.", "Üretim Ekipmanı", "FMEA No", "Özel Karakteristik",
             "Kontrol Yöntemi", "Alternatif Yöntem", "Acil Eylem Planı", "DÖF Planı", "Tip"]


def kp_satirlari(kod):
    """LeanSys kontrol planı satırları — modüldeki sıralamayla (op no, sıra no)."""
    r = sorgu("/leansys_kontrol_plani?stok_kodu=eq.%s&limit=500" % urllib.parse.quote(kod))
    return sorted(r, key=lambda x: (x.get("op_no") or 0, x.get("sira_no") or 0))


def pl41_kontrol_plani(v, hedef):
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter

    satirlar = kp_satirlari(v["kod"])
    if not satirlar:
        return 0
    ilk = satirlar[0]

    wb = Workbook(); ws = wb.active; ws.title = "Kontrol Planı"
    ws.sheet_view.showGridLines = False
    ince = Side(style="thin", color="888888")
    kutu = Border(top=ince, bottom=ince, left=ince, right=ince)
    W = len(KP_BASLIK)

    def koy(r, c, deger, kalin=False, boyut=9, renk=None, zemin=None,
            yatay="left", genislik=1, yukseklik=1):
        for rr in range(r, r + yukseklik):
            for cc in range(c, c + genislik):
                h = ws.cell(rr, cc, deger if (rr == r and cc == c) else None)
                h.border = kutu
                h.font = Font(bold=kalin, size=boyut, color=renk or "1F2937")
                h.alignment = Alignment(horizontal=yatay, vertical="center", wrap_text=True)
                if zemin:
                    h.fill = PatternFill("solid", fgColor=zemin)
        if genislik > 1 or yukseklik > 1:
            ws.merge_cells(start_row=r, start_column=c, end_row=r + yukseklik - 1,
                           end_column=c + genislik - 1)

    # ── Üst bant: logo | başlık | doküman kontrol kutusu
    koy(1, 1, "SANİFOAM", True, 15, "1D4ED8", None, "center", 3, 4)
    koy(1, 4, "KONTROL PLANI", True, 16, "0D3055", None, "center", 13, 4)
    dkutu = [("Dok.No", "PL 41"), ("Yayın Trh.", met(ilk.get("plan_onay"))[:10]),
             ("Rev. No/Trh", "%s / %s" % (met(ilk.get("rev_no")), met(ilk.get("plan_onay"))[:10])),
             ("Sayfa", "1/1")]
    for i, (e, d) in enumerate(dkutu):
        koy(1 + i, 17, e, True, 8, None, "E8E8E8", "left", 2)
        koy(1 + i, 19, d, False, 8, None, None, "left", 4)

    # ── Meta ızgara (modüldeki 4 satır)
    tarih = lambda a: met(ilk.get(a))[:10]
    meta = [
        [("Stok Kodu", 1, 2), (v["kod"], 0, 2), ("Stok Adı", 1, 2), (v["ad"], 0, 10),
         ("Kontrol Tipi", 1, 3), (met(ilk.get("tip")), 0, 3)],
        [("Cari Kartı", 1, 2), (v["musteri"], 0, 3), ("İlgili Kişi", 1, 2),
         (met(ilk.get("ilgili_kisi")), 0, 3), ("Çekirdek Takım", 1, 3),
         (met(ilk.get("cekirdek_takim")), 0, 3), ("Tolerans Tablosu", 1, 3), ("", 0, 3)],
        [("Müh. Onay", 1, 3), (tarih("muh_onay"), 0, 2), ("Kalite Onay", 1, 3),
         (tarih("klt_onay"), 0, 2), ("Plan Onay", 1, 3), (tarih("plan_onay"), 0, 2),
         ("Diğer Onay", 1, 3), (tarih("diger_onay"), 0, 4)],
        [("Tek. Resim Rev No", 1, 4), (met(ilk.get("tr_revno")), 0, 2),
         ("Tek. Resim Rev Tarihi", 1, 4), (tarih("tr_revtarih"), 0, 2),
         ("Kontrol Planı No", 1, 3), (met(ilk.get("plan_no")), 0, 2),
         ("Revizyon Nedeni", 1, 3), ("", 0, 2)],
    ]
    for ri, parcalar in enumerate(meta):
        c = 1
        for deger, etiket, genis in parcalar:
            koy(5 + ri, c, deger, bool(etiket), 9, None,
                "E8E8E8" if etiket else None, "left", genis)
            c += genis

    # ── Tablo başlığı + veri
    for i, b in enumerate(KP_BASLIK):
        koy(10, 1 + i, b, True, 9, "FFFFFF", "1D4ED8", "center")
    ws.row_dimensions[10].height = 28

    isaret = lambda x: "✓" if x else "—"
    for i, x in enumerate(satirlar):
        nitel = met(x.get("hedef_nitel"))
        deg = [i + 1, met(x.get("operasyon_karti")), x.get("op_no"),
               isaret(x.get("proses_kontrol")), isaret(x.get("giris")), isaret(x.get("son_kontrol")),
               met(x.get("olculecek")), x.get("hedef_nicel"), nitel,
               x.get("alt_limit"), x.get("ust_limit"), x.get("ornekleme_buyuklugu"),
               x.get("ornekleme_sikligi"), x.get("son_ornekleme"), met(x.get("uretim_ekipman")),
               met(x.get("fmea_no")), met(x.get("ozel_kar")), met(x.get("yontem")), "",
               met(x.get("acil_eylem")), met(x.get("dof_plan")),
               "Nitel" if nitel and x.get("hedef_nicel") in (None, "") else "Ölçüm"]
        r = 11 + i
        for j, d in enumerate(deg):
            h = ws.cell(r, 1 + j, d if d not in (None, "") else "")
            h.border = kutu
            h.font = Font(size=9)
            h.alignment = Alignment(vertical="top", wrap_text=True,
                                    horizontal="center" if j in (0, 2, 3, 4, 5) else "left")
            if i % 2:
                h.fill = PatternFill("solid", fgColor="F4F7FB")

    for i in range(W):
        ws.column_dimensions[get_column_letter(1 + i)].width = (
            7 if i == 0 else 30 if i == 6 else 24 if i == 8 else 16 if i >= 14 else 11)
    ws.freeze_panes = "A11"
    ws.page_setup.orientation = "landscape"
    ws.print_area = "A1:%s%d" % (get_column_letter(W), 10 + len(satirlar))
    wb.save(hedef)
    return len(satirlar)


# ── FR34 P-FMEA (PFMEA modülünün kendi Excel düzeni — 30 sütun, AIAG-VDA) ──
FMEA_BASLIK = [
    "1. Process Item System, Subsystem, Part Element or Name of Process",
    "2. Process Step Station No. and Name of Focus Element",
    "3. Process Work Element 4M Type",
    "1. Function of the Process Item Function of System, Subsystem, Part Element or Process",
    "2. Function of the Process Step and Product Characteristic",
    "3. Function of the Process Work Element and Process Characteristic",
    "1. Failure Effect (FE) for the Next Higher Level and/or End User", "Severity (S) of FE",
    "2. Failure Mode (FM) of the Focus Element", "3. Failure Cause (FC) of the Work Element",
    "Current Prevention Control (PC) of FC", "Occurrence (O) of FC",
    "Current Detection Control (DC) of FC or FM", "Detection (D) of FC/FM", "PFMEA AP",
    "Spec. Characteristic", "Filter Code (Optional)", "Prevention Action", "Detection Action",
    "Responsible Person's Name", "Target Completion Date", "Status",
    "Action Taken with Pointer to Evidence", "Completion Date", "Severity (S)", "Occurrence (O)",
    "Detection (D)", "Spec. Characteristic", "PFMEA AP", "Remarks"]
FMEA_GRUP = [(0, 2, "Structure analysis (Step 2)"), (3, 5, "Function analysis (Step 3)"),
             (6, 9, "Failure analysis (Step 4)"), (10, 16, "Risk analysis (Step 5)"),
             (17, 29, "Optimization (Step 6)")]
FMEA_GENIS = [20, 20, 15, 20, 25, 20, 25, 5, 25, 25, 20, 5, 20, 5, 5, 10, 10, 20, 20, 15,
              15, 10, 25, 15, 5, 5, 5, 10, 5, 20]
AP_RENK = {"H": "FFC7CE", "M": "FFEB9C", "L": "C6EFCE"}


def fmea_projesi(v):
    """Bu ürünün PFMEA projesi. Ad, müşteri parça no veya stok kodu ile eşleşir."""
    hepsi = sorgu("/pfmea_projects?select=id,name,data")
    aday = [v["kod"]] + ([met(v.get("musteriParca"))] if met(v.get("musteriParca")) else [])
    aday += [met(v["ad"]).split()[0]] if met(v["ad"]) else []
    for a in aday:
        if not a:
            continue
        for x in hepsi:
            if a.lower() in met(x.get("name")).lower():
                return x
    # PFMEA projesi kendi adının içinde stok kodunu parantezle taşıyor olabilir
    for x in hepsi:
        d = (x.get("data") or {}).get("fmeaData") or {}
        for it in (d.get("processItems") or {}).values():
            if v["kod"].lower() in met(it.get("name")).lower():
                return x
    return None


def fr34_pfmea(v, hedef):
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter

    proje = fmea_projesi(v)
    if not proje:
        return 0
    d = (proje.get("data") or {}).get("fmeaData") or {}
    f = ((proje.get("data") or {}).get("projectData") or {}).get("fmea") or {}
    ITEM = d.get("processItems") or {}
    STEP = d.get("processSteps") or {}
    FUNC = d.get("processStepFunctions") or {}
    MODE = d.get("failureModes") or {}
    CAUSE = d.get("failureCauses") or {}
    EFFECT = d.get("failureEffects") or {}

    wb = Workbook(); ws = wb.active; ws.title = "FMEA"
    ws.sheet_view.showGridLines = False
    ince = Side(style="thin", color="808080")
    kutu = Border(top=ince, bottom=ince, left=ince, right=ince)

    antet(ws, "PROCESS FAILURE MODES & EFFECTS ANALYSIS\n(PROSES FMEA)", "FR 34",
          "02.01.2025", "4", "1 / 1", 30)
    r = 6
    b = ws.cell(r, 1, "Process Failure Mode and Effects Analysis (Process FMEA)")
    b.font = Font(bold=True, size=13, color="0D3055")
    b.alignment = Alignment(horizontal="center", vertical="center")
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=30)
    r += 2

    # Proje bilgi bloğu — modüldeki 3 sütunlu düzen
    bilgi = [("Project:", f.get("project")), ("Client:", f.get("client")),
             ("Number/Name of product:", f.get("productName")), ("Project ID:", f.get("projectId")),
             ("Engineering Location:", f.get("engineeringLocation")),
             ("Date of first FMEA:", f.get("firstFmeaDate")),
             ("Person responsible:", f.get("personResponsible")),
             ("FMEA Creator:", f.get("fmeaCreator")),
             ("Last revision date:", f.get("lastRevisionDate")),
             ("FMEA Number /Version:", f.get("fmeaNumberVersion")),
             ("FMEA Approver:", f.get("fmeaApprover")), ("Company name:", f.get("companyName"))]

    def alan(sat, sut, etiket, deger):
        e = ws.cell(sat, sut, etiket)
        e.font = Font(bold=True, size=9); e.border = kutu
        e.fill = PatternFill("solid", fgColor="EDF2F7")
        e.alignment = Alignment(vertical="center", wrap_text=True)
        g = ws.cell(sat, sut + 1, met(deger) or "-")
        g.font = Font(size=9); g.border = kutu
        g.alignment = Alignment(vertical="center", wrap_text=True)
        for c in range(sut + 1, sut + 5):
            ws.cell(sat, c).border = kutu
        ws.merge_cells(start_row=sat, start_column=sut + 1, end_row=sat, end_column=sut + 5)

    for i in range(4):
        alan(r, 1, *bilgi[i]); alan(r, 7, *bilgi[i + 4]); alan(r, 13, *bilgi[i + 8])
        r += 1
    for etiket, deger in (("Team members:", f.get("teamMembers")), ("Notes/comments:", f.get("notes"))):
        if met(deger):
            e = ws.cell(r, 1, etiket); e.font = Font(bold=True, size=9); e.border = kutu
            e.fill = PatternFill("solid", fgColor="EDF2F7")
            g = ws.cell(r, 2, met(deger)); g.font = Font(size=9); g.border = kutu
            g.alignment = Alignment(vertical="center", wrap_text=True)
            ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=30)
            r += 1
    r += 1

    # Tablo başlığı: grup satırı + 2 satır birleşik sütun başlığı
    for bas, son, ad in FMEA_GRUP:
        h = ws.cell(r, 1 + bas, ad)
        h.font = Font(bold=True, size=10, color="FFFFFF")
        h.fill = PatternFill("solid", fgColor="1F3864")
        h.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        for c in range(bas, son + 1):
            ws.cell(r, 1 + c).border = kutu
            ws.cell(r, 1 + c).fill = PatternFill("solid", fgColor="1F3864")
        ws.merge_cells(start_row=r, start_column=1 + bas, end_row=r, end_column=1 + son)
    for i, b in enumerate(FMEA_BASLIK):
        h = ws.cell(r + 1, 1 + i, b)
        h.font = Font(bold=True, size=8, color="FFFFFF")
        h.fill = PatternFill("solid", fgColor="2E5496")
        h.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        for rr in (r + 1, r + 2):
            ws.cell(rr, 1 + i).border = kutu
            ws.cell(rr, 1 + i).fill = PatternFill("solid", fgColor="2E5496")
        ws.merge_cells(start_row=r + 1, start_column=1 + i, end_row=r + 2, end_column=1 + i)
    ws.row_dimensions[r + 1].height = 58
    r += 3

    # Gövde: item > step > function > mode > cause (modüldeki satır açılımı)
    birlestir = []          # (bas, son, sutun, deger) — kaynak satırı bittiğinde uygulanır
    zebra = False
    bas_satir = r
    for iid in (d.get("processItemIds") or list(ITEM.keys())):
        it = ITEM.get(iid) or {}
        for sid in (it.get("stepIds") or []):
            st = STEP.get(sid) or {}
            zebra = not zebra
            adim_bas = r
            for fid in (st.get("functionIds") or []):
                fn = FUNC.get(fid) or {}
                fonk_bas = r
                for mid in (fn.get("failureModeIds") or []):
                    md = MODE.get(mid) or {}
                    mod_bas = r
                    etkiler = [EFFECT.get(e) or {} for e in (md.get("effectIds") or [])]
                    etki_metin = "\n".join("[%s] %s" % (met(e.get("clientType")), met(e.get("effectText")))
                                           for e in etkiler)
                    for cid in (md.get("causeIds") or [None]):
                        cz = CAUSE.get(cid) or {}
                        eylem = cz.get("actions") or []
                        birles = lambda alan_ad, tur=None: "\n".join(
                            met(a.get(alan_ad)) for a in eylem
                            if met(a.get(alan_ad)) and (tur is None or a.get("type") == tur))
                        siddet = cz.get("severity")
                        if siddet is None and etkiler:
                            siddet = max([e.get("severity") or 0 for e in etkiler])
                        deger = [
                            met(it.get("name")), "[%s] %s" % (met(st.get("operationNumber")), met(st.get("name"))),
                            met(cz.get("processWorkElement")), met(it.get("name")),
                            (met(fn.get("name")) + "\n" + met(fn.get("productCharacteristic"))).strip(),
                            met(cz.get("workElementFunction")), etki_metin, siddet,
                            met(md.get("description")), met(cz.get("description")),
                            met(cz.get("preventionControl")), cz.get("occurrence"),
                            met(cz.get("detectionControl")), cz.get("detection"),
                            met(cz.get("actionPriority")), met(fn.get("specialCharacteristic")),
                            met(cz.get("filterCode")), birles("description", "prevention"),
                            birles("description", "detection"), birles("responsiblePerson"),
                            birles("targetCompletionDate"), birles("status"), birles("actionTaken"),
                            birles("completionDate"), cz.get("revisedSeverity"),
                            cz.get("revisedOccurrence"), cz.get("revisedDetection"),
                            met(fn.get("specialCharacteristic")),
                            "(%s)" % cz["revisedActionPriority"] if cz.get("revisedActionPriority") else "",
                            met(cz.get("remarks"))]
                        for j, x in enumerate(deger):
                            h = ws.cell(r, 1 + j, x if x not in (None, "") else "")
                            h.border = kutu
                            h.font = Font(size=8)
                            h.alignment = Alignment(vertical="top", wrap_text=True,
                                                    horizontal="center" if j in (7, 11, 13, 14, 24, 25, 26, 28) else "left")
                            if zebra:
                                h.fill = PatternFill("solid", fgColor="F4F7FB")
                            if j in (14, 28):
                                renk = AP_RENK.get(str(x or "").strip("()").upper())
                                if renk:
                                    h.fill = PatternFill("solid", fgColor=renk)
                        r += 1
                    if r - mod_bas > 1:
                        birlestir += [(mod_bas, r - 1, c) for c in (7, 9)]
                if r - fonk_bas > 1:
                    birlestir.append((fonk_bas, r - 1, 5))
            if r - adim_bas > 1:
                birlestir += [(adim_bas, r - 1, c) for c in (1, 2, 4)]
    for b1, b2, c in birlestir:
        ws.merge_cells(start_row=b1, start_column=c, end_row=b2, end_column=c)

    for i, g in enumerate(FMEA_GENIS):
        ws.column_dimensions[get_column_letter(1 + i)].width = g
    ws.freeze_panes = "A%d" % bas_satir
    ws.page_setup.orientation = "landscape"
    wb.save(hedef)
    return r - bas_satir


# ── MSA: kontrol planındaki ölçüm aletleri ───────────────────────────────
# Nitel (gözle/görsel) aletler AIAG MSA 4th Ed. Type-3 nitelik uyum analizine,
# ölçüm aletleri Type-1 (Cg/Cgk) + Type-2 Gage R&R'a yönlendirilir.
NITEL_ALET = ("GÖZLE", "GÖRSEL", "GOZLE", "GORSEL", "TL")


def msa_aletleri(kod):
    """Kontrol planındaki her ölçüm aleti için: en dar tolerans, karakteristikler."""
    gruplar = {}
    for x in kp_satirlari(kod):
        alet = met(x.get("yontem")).strip()
        if not alet:
            continue
        anahtar = alet.upper()
        g = gruplar.setdefault(anahtar, {"alet": alet, "kar": [], "tol": None, "op": set()})
        g["kar"].append(met(x.get("olculecek")))
        g["op"].add(str(x.get("op_no")))
        alt, ust = x.get("alt_limit"), x.get("ust_limit")
        if alt is not None and ust is not None:
            try:
                t = float(ust) - float(alt)
                if t > 0 and (g["tol"] is None or t < g["tol"]):
                    g["tol"] = t
                    g["dar_kar"] = met(x.get("olculecek"))
                    g["dar_limit"] = "%s – %s" % (alt, ust)
            except (TypeError, ValueError):
                pass
    for g in gruplar.values():
        g["nitel"] = g["tol"] is None or g["alet"].upper().startswith(NITEL_ALET)
        g["kar"] = list(dict.fromkeys(g["kar"]))
    return list(gruplar.values())


def msa_plani(v, hedef):
    """MSA Planı: hangi alet, hangi karakteristik, hangi MSA tipi, kim, ne zaman."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter

    aletler = msa_aletleri(v["kod"])
    if not aletler:
        return 0
    wb = Workbook(); ws = wb.active; ws.title = "MSA Planı"
    ws.sheet_view.showGridLines = False
    ince = Side(style="thin", color="808080")
    kutu = Border(top=ince, bottom=ince, left=ince, right=ince)
    for h, g in zip("ABCDEFGHI", (6, 22, 34, 12, 26, 26, 16, 14, 20)):
        ws.column_dimensions[h].width = g

    antet(ws, "ÖLÇÜM SİSTEMİ ANALİZİ (MSA) PLANI", "FR 86-P",
          "02.01.2025", "0", "1 / 1", 9)
    r = 6
    for etiket, deger in (("Ürün :", "%s — %s" % (v["kod"], v["ad"])),
                          ("Müşteri :", v["musteri"]),
                          ("Lokasyon :", v["lokasyon_ad"]),
                          ("Kaynak :", "Leansys PL41 Kontrol Planı — ölçüm yöntemi sütunu")):
        e = ws.cell(r, 1, etiket); e.font = Font(bold=True, size=10)
        e.alignment = Alignment(horizontal="right")
        g = ws.cell(r, 2, deger); g.alignment = Alignment(vertical="center")
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=9)
        r += 1
    r += 1

    basliklar = ["No", "Ölçüm Aleti", "Ölçülen Karakteristik(ler)", "Op No",
                 "En Dar Tolerans", "MSA Tipi (AIAG MSA 4. Baskı)", "Kabul Kriteri",
                 "Sorumlu", "Planlanan Tarih"]
    for i, b in enumerate(basliklar):
        h = ws.cell(r, 1 + i, b)
        h.font = Font(bold=True, size=10, color="FFFFFF")
        h.fill = PatternFill("solid", fgColor="1F3864"); h.border = kutu
        h.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[r].height = 32
    bas = r
    rolAd = dict((rol, ad) for rol, ad in v["ekip"])
    sorumlu = rolAd.get("Kalite Mühendisi") or rolAd.get("Kalite Güvence Müdürü")

    for i, g in enumerate(sorted(aletler, key=lambda x: (x["nitel"], x["alet"]))):
        if g["nitel"]:
            tip = ("Type-3 Nitelik Uyum Analizi\n(3 kontrolör × 30 parça × 2 tekrar, Kappa)")
            kriter = "Kappa ≥ 0,75 ve kontrolör içi/arası uyum ≥ %90"
            tol = "Nitel — tolerans yok"
        else:
            tip = ("Type-1 (Cg/Cgk) + Type-2 Gage R&R\n(3 operatör × 10 parça × 3 tekrar, ANOVA)")
            kriter = "Cg/Cgk ≥ 1,33 ; %GRR ≤ %10 kabul, %10–30 şartlı, ndc ≥ 5"
            tol = "%s  (%s)" % (("%g" % g["tol"]), g.get("dar_kar", "")[:26])
        deger = [i + 1, g["alet"], ", ".join(g["kar"])[:220], ", ".join(sorted(g["op"])),
                 tol, tip, kriter, sorumlu, v["termin"]]
        rr = bas + 1 + i
        for j, x in enumerate(deger):
            h = ws.cell(rr, 1 + j, x)
            h.border = kutu; h.font = Font(size=9)
            h.alignment = Alignment(wrap_text=True, vertical="center",
                                    horizontal="center" if j in (0, 3, 8) else "left")
            if i % 2:
                h.fill = PatternFill("solid", fgColor="F4F7FB")
        ws.row_dimensions[rr].height = 40

    rr = bas + len(aletler) + 2
    ws.cell(rr, 1, "Ölçüm değerleri MSA modülünde (ERP) girilir; bu plan hangi alet için hangi "
                   "çalışmanın yapılacağını ve kabul kriterini tanımlar.").font = \
        Font(size=8, italic=True, color="808080")
    ws.merge_cells(start_row=rr, start_column=1, end_row=rr, end_column=9)
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    wb.save(hedef)
    return len(aletler)


def fr86_gage_rr(v, hedef):
    """FR86 Gage R&R — her ölçüm aleti için ayrı sayfa. Ölçüm hücreleri BOŞ;
    EV/AV/GRR/PV/TV/%GRR/ndc AIAG MSA 4. Baskı ortalama-aralık yöntemiyle
    canlı formüllüdür, operatör ölçünce sonuç kendiliğinden çıkar.
    Nitel aletler için Type-3 nitelik uyum sayfası üretilir."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill
    from openpyxl.utils import get_column_letter

    hepsi = msa_aletleri(v["kod"])
    olcum = [g for g in hepsi if not g["nitel"]]
    nitel = [g for g in hepsi if g["nitel"]]
    if not hepsi:
        return 0
    wb = Workbook(); wb.remove(wb.active)
    rolAd = dict((rol, ad) for rol, ad in v["ekip"])
    OPS, PARCA, TEKRAR = 3, 10, 3
    # AIAG MSA 4. Baskı K katsayıları (6σ, d2* tablosundan)
    K1 = {2: 0.8862, 3: 0.5908}[TEKRAR]      # tekrarlanabilirlik
    K2 = {2: 0.7071, 3: 0.5231}[OPS]         # tekrar üretilebilirlik
    K3 = {5: 0.4030, 10: 0.3146}[PARCA]      # parça değişkenliği
    SUT = lambda i: get_column_letter(i)

    def sayfa_basligi(ws, g, baslik, dok):
        ws.sheet_view.showGridLines = False
        antet(ws, baslik, dok, "02.01.2025", "0", "1 / 1", 13)
        r = 6
        for etiket, deger in (("Ürün :", "%s — %s" % (v["kod"], v["ad"])),
                              ("Ölçüm Aleti :", g["alet"]),
                              ("Karakteristik :", g.get("dar_kar") or ", ".join(g["kar"])[:70]),
                              ("Tolerans :", "%s   (aralık %g)" % (g.get("dar_limit", "—"), g["tol"])
                               if g.get("tol") else "Nitel — kabul/ret"),
                              ("Sorumlu :", rolAd.get("Kalite Mühendisi", "")),
                              ("Tarih :", v["termin"])):
            e = ws.cell(r, 1, etiket); e.font = Font(bold=True, size=10)
            e.alignment = Alignment(horizontal="right")
            ws.cell(r, 2, deger).alignment = Alignment(vertical="center")
            ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=13)
            r += 1
        return r + 1

    def baslik_hucre(ws, r, c, metin, genis=1):
        h = ws.cell(r, c, metin)
        h.font = Font(bold=True, size=9, color="FFFFFF")
        h.fill = PatternFill("solid", fgColor="1F3864")
        h.border = kutu_ince
        h.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        for cc in range(c, c + genis):
            ws.cell(r, cc).border = kutu_ince
            ws.cell(r, cc).fill = PatternFill("solid", fgColor="1F3864")
        if genis > 1:
            ws.merge_cells(start_row=r, start_column=c, end_row=r, end_column=c + genis - 1)

    from openpyxl.styles import Border, Side
    _i = Side(style="thin", color="808080")
    kutu_ince = Border(top=_i, bottom=_i, left=_i, right=_i)

    # ── Ölçüm aletleri: Type-2 Gage R&R (ANOVA yerine ortalama-aralık) ────
    for g in olcum:
        ad = re.sub(r"[\\/*?:\[\]]", "-", g["alet"])[:28]
        ws = wb.create_sheet(ad)
        for h, gen in zip("ABCDEFGHIJKLM", (11, 8, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 11)):
            ws.column_dimensions[h].width = gen
        r = sayfa_basligi(ws, g, "GAGE R&R (ÖLÇÜM SİSTEMİ ANALİZİ)", "FR 86")

        baslik_hucre(ws, r, 1, "Operatör"); baslik_hucre(ws, r, 2, "Tekrar")
        for pz in range(PARCA):
            baslik_hucre(ws, r, 3 + pz, "Parça %d" % (pz + 1))
        baslik_hucre(ws, r, 3 + PARCA, "Ortalama")
        r += 1
        op_bas = r
        op_ort = []                                  # her operatörün ortalama hücresi
        for o in range(OPS):
            for t in range(TEKRAR):
                c1 = ws.cell(r, 1, "Operatör %s" % chr(65 + o) if t == 0 else None)
                c1.font = Font(bold=True, size=9)
                c1.alignment = Alignment(horizontal="center", vertical="center")
                c1.border = kutu_ince
                c2 = ws.cell(r, 2, t + 1)
                c2.alignment = Alignment(horizontal="center"); c2.border = kutu_ince
                for pz in range(PARCA):
                    c = ws.cell(r, 3 + pz)
                    c.border = kutu_ince; c.number_format = "0.000"
                    c.fill = PatternFill("solid", fgColor="FFFDE7")   # doldurulacak
                ws.cell(r, 3 + PARCA).border = kutu_ince
                r += 1
            blok = "%s%d:%s%d" % (SUT(3), r - TEKRAR, SUT(2 + PARCA), r - 1)
            h = ws.cell(r - TEKRAR, 3 + PARCA, "=IFERROR(AVERAGE(%s),\"\")" % blok)
            h.number_format = "0.000"; h.font = Font(bold=True, size=9)
            h.alignment = Alignment(horizontal="center", vertical="center")
            ws.merge_cells(start_row=r - TEKRAR, start_column=1, end_row=r - 1, end_column=1)
            ws.merge_cells(start_row=r - TEKRAR, start_column=3 + PARCA, end_row=r - 1,
                           end_column=3 + PARCA)
            op_ort.append("%s%d" % (SUT(3 + PARCA), r - TEKRAR))
        grid_son = r - 1
        tum = "%s%d:%s%d" % (SUT(3), op_bas, SUT(2 + PARCA), grid_son)

        # Aralık bloğu: her operatör × parça için (maks − min)
        r += 1
        baslik_hucre(ws, r, 1, "Aralık (R)", 2)
        for pz in range(PARCA):
            baslik_hucre(ws, r, 3 + pz, "Parça %d" % (pz + 1))
        r += 1
        rng_bas = r
        for o in range(OPS):
            e = ws.cell(r, 1, "Operatör %s" % chr(65 + o))
            e.font = Font(bold=True, size=9); e.border = kutu_ince
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=2)
            ws.cell(r, 2).border = kutu_ince
            for pz in range(PARCA):
                sut = SUT(3 + pz)
                ilk = op_bas + o * TEKRAR
                c = ws.cell(r, 3 + pz, "=IFERROR(MAX(%s%d:%s%d)-MIN(%s%d:%s%d),\"\")"
                            % (sut, ilk, sut, ilk + TEKRAR - 1, sut, ilk, sut, ilk + TEKRAR - 1))
                c.number_format = "0.000"; c.border = kutu_ince
                c.alignment = Alignment(horizontal="center")
            r += 1
        rng_son = r - 1
        # Parça ortalamaları (PV için)
        e = ws.cell(r, 1, "Parça ortalaması")
        e.font = Font(bold=True, size=9); e.border = kutu_ince
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=2)
        ws.cell(r, 2).border = kutu_ince
        for pz in range(PARCA):
            sut = SUT(3 + pz)
            c = ws.cell(r, 3 + pz, "=IFERROR(AVERAGE(%s%d:%s%d),\"\")"
                        % (sut, op_bas, sut, grid_son))
            c.number_format = "0.000"; c.border = kutu_ince
            c.alignment = Alignment(horizontal="center")
        pavg = r
        r += 2

        # Hesap bloğu — AIAG MSA 4. Baskı, 6σ
        rbar = "AVERAGE(%s%d:%s%d)" % (SUT(3), rng_bas, SUT(2 + PARCA), rng_son)
        xdiff = "MAX(%s)-MIN(%s)" % (",".join(op_ort), ",".join(op_ort))
        rp = "MAX(%s%d:%s%d)-MIN(%s%d:%s%d)" % (SUT(3), pavg, SUT(2 + PARCA), pavg,
                                                SUT(3), pavg, SUT(2 + PARCA), pavg)
        hesap = [
            ("Ölçüm sayısı (hedef %d)" % (OPS * PARCA * TEKRAR), "=COUNT(%s)" % tum, "0"),
            ("R̄  — ortalama aralık", "=IFERROR(%s,\"\")" % rbar, "0.0000"),
            ("X̄diff — operatör ortalamaları farkı", "=IFERROR(%s,\"\")" % xdiff, "0.0000"),
            ("Rp — parça ortalamaları aralığı", "=IFERROR(%s,\"\")" % rp, "0.0000"),
            ("EV = R̄ × K1  (K1=%.4f)" % K1, None, "0.0000"),
            ("AV = √((X̄diff×K2)² − EV²/(n·r))  (K2=%.4f)" % K2, None, "0.0000"),
            ("GRR = √(EV² + AV²)", None, "0.0000"),
            ("PV = Rp × K3  (K3=%.4f)" % K3, None, "0.0000"),
            ("TV = √(GRR² + PV²)", None, "0.0000"),
            ("Tolerans", "=%g" % g["tol"], "0.0000"),
            ("%GRR (toleransa göre)", None, "0.0%"),
            ("%GRR (TV'ye göre)", None, "0.0%"),
            ("ndc = 1,41 × PV / GRR", None, "0.0"),
            ("SONUÇ", None, "@"),
        ]
        hbas = r
        for etiket, formul, bicim in hesap:
            e = ws.cell(r, 1, etiket)
            e.font = Font(bold=True, size=9); e.border = kutu_ince
            e.alignment = Alignment(horizontal="left", vertical="center")
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5)
            for cc in range(1, 6):
                ws.cell(r, cc).border = kutu_ince
            c = ws.cell(r, 6, formul)
            c.border = kutu_ince; c.number_format = bicim
            c.font = Font(bold=True, size=9)
            c.alignment = Alignment(horizontal="center", vertical="center")
            r += 1
        F = lambda i: "F%d" % (hbas + i)
        ws[F(4)] = "=IFERROR(%s*%.4f,\"\")" % (F(1), K1)
        ws[F(5)] = ("=IFERROR(SQRT(MAX(0,(%s*%.4f)^2-(%s^2/%d))),\"\")"
                    % (F(2), K2, F(4), PARCA * TEKRAR))
        ws[F(6)] = "=IFERROR(SQRT(%s^2+%s^2),\"\")" % (F(4), F(5))
        ws[F(7)] = "=IFERROR(%s*%.4f,\"\")" % (F(3), K3)
        ws[F(8)] = "=IFERROR(SQRT(%s^2+%s^2),\"\")" % (F(6), F(7))
        ws[F(10)] = "=IFERROR(%s/%s,\"\")" % (F(6), F(9))
        ws[F(11)] = "=IFERROR(%s/%s,\"\")" % (F(6), F(8))
        ws[F(12)] = "=IFERROR(1.41*%s/%s,\"\")" % (F(7), F(6))
        # Karar, toleransa ve toplam degiskenlige gore %GRR'lerin KOTUSUNE
        # baglidir; yalniz toleransa bakmak olcum sistemini iyi gosterebilir.
        kotu = "MAX(%s,%s)" % (F(10), F(11))
        ws[F(13)] = ('=IF(%s<%d,"ölçüm bekleniyor ("&%s&"/%d)",'
                     'IF(AND(%s<=0.1,%s>=5),"KABUL — %%GRR ≤ %%10 ve ndc ≥ 5",'
                     'IF(%s<=0.3,"ŞARTLI KABUL — %%10–30, iyileştirme gerekli",'
                     '"RED — %%GRR > %%30, ölçüm sistemi yetersiz")))'
                     % (F(0), OPS * PARCA * TEKRAR, F(0), OPS * PARCA * TEKRAR,
                        kotu, F(12), kotu))
        ws.cell(r + 1, 1, "Sarı hücrelere ölçüm değerleri girilir (10 parça, 3 operatör, 3 tekrar; "
                          "parçalar proses değişkenliğini temsil etmeli, sıra karıştırılmalı). "
                          "Kabul: %GRR ≤ %10 ve ndc ≥ 5 — AIAG MSA 4. Baskı, ortalama-aralık yöntemi."
                ).font = Font(size=8, italic=True, color="808080")
        ws.merge_cells(start_row=r + 1, start_column=1, end_row=r + 1, end_column=13)
        ws.page_setup.orientation = "landscape"

    # ── Nitel aletler: Type-3 nitelik uyum analizi (kappa) ────────────────
    NP = 30
    for g in nitel:
        ad = ("N-" + re.sub(r"[\\/*?:\[\]]", "-", g["alet"]))[:28]
        ws = wb.create_sheet(ad)
        for h, gen in zip("ABCDEFGHI", (8, 14, 10, 10, 10, 10, 10, 10, 14)):
            ws.column_dimensions[h].width = gen
        r = sayfa_basligi(ws, g, "NİTELİK UYUM ANALİZİ (ATTRIBUTE MSA)", "FR 86-N")

        basliklar = ["Parça", "Referans\n(OK/NOK)", "A-1", "A-2", "B-1", "B-2", "C-1", "C-2",
                     "Uyum"]
        for i, b in enumerate(basliklar):
            baslik_hucre(ws, r, 1 + i, b)
        ws.row_dimensions[r].height = 28
        r += 1
        vbas = r
        for i in range(NP):
            ws.cell(r, 1, i + 1).alignment = Alignment(horizontal="center")
            for c in range(1, 9):
                h = ws.cell(r, c)
                h.border = kutu_ince
                h.alignment = Alignment(horizontal="center")
                if c >= 2:
                    h.fill = PatternFill("solid", fgColor="FFFDE7")
            # Tum degerlendirmeler referansla ayni mi?
            ws.cell(r, 9, '=IF(COUNTA(C%d:H%d)<6,"",IF(COUNTIF(C%d:H%d,B%d)=6,1,0))'
                    % (r, r, r, r, r)).border = kutu_ince
            ws.cell(r, 9).alignment = Alignment(horizontal="center")
            r += 1
        vson = r - 1
        r += 1
        ikili = [("A", "C", "D"), ("B", "E", "F"), ("C", "G", "H")]
        hesap = [("Değerlendirilen parça sayısı", "=COUNT(I%d:I%d)" % (vbas, vson), "0")]
        for kim, s1, s2 in ikili:
            hesap.append(("Kontrolör %s — kendi içinde uyum" % kim,
                          '=IFERROR(SUMPRODUCT(--(%s%d:%s%d=%s%d:%s%d))/COUNTA(%s%d:%s%d),"")'
                          % (s1, vbas, s1, vson, s2, vbas, s2, vson, s1, vbas, s1, vson), "0.0%"))
        for kim, s1, s2 in ikili:
            hesap.append(("Kontrolör %s — referansa uyum" % kim,
                          '=IFERROR((SUMPRODUCT(--(%s%d:%s%d=B%d:B%d))+SUMPRODUCT(--(%s%d:%s%d=B%d:B%d)))'
                          '/(2*COUNTA(B%d:B%d)),"")'
                          % (s1, vbas, s1, vson, vbas, vson, s2, vbas, s2, vson, vbas, vson,
                             vbas, vson), "0.0%"))
        hesap += [
            ("Tüm kontrolörler + referans tam uyum (Po)",
             '=IFERROR(AVERAGE(I%d:I%d),"")' % (vbas, vson), "0.0%"),
            ("Beklenen uyum (Pe)", None, "0.0%"),
            ("Kappa = (Po − Pe) / (1 − Pe)", None, "0.000"),
            ("SONUÇ", None, "@"),
        ]
        hbas = r
        for etiket, formul, bicim in hesap:
            e = ws.cell(r, 1, etiket)
            e.font = Font(bold=True, size=9); e.border = kutu_ince
            e.alignment = Alignment(horizontal="left", vertical="center")
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
            for cc in range(1, 7):
                ws.cell(r, cc).border = kutu_ince
            c = ws.cell(r, 7, formul)
            c.border = kutu_ince; c.number_format = bicim
            c.font = Font(bold=True, size=9)
            c.alignment = Alignment(horizontal="center", vertical="center")
            r += 1
        G = lambda i: "G%d" % (hbas + i)
        # Pe: referanstaki OK/NOK oranlarının karesi toplamı
        ws[G(8)] = ('=IFERROR((COUNTIF(B{0}:B{1},"OK")/COUNTA(B{0}:B{1}))^2'
                    '+(COUNTIF(B{0}:B{1},"NOK")/COUNTA(B{0}:B{1}))^2,"")').format(vbas, vson)
        ws[G(9)] = '=IFERROR((%s-%s)/(1-%s),"")' % (G(7), G(8), G(8))
        ws[G(10)] = ('=IF(%s="","ölçüm bekleniyor",IF(AND(%s>=0.75,%s>=0.9),'
                     '"KABUL — Kappa ≥ 0,75 ve uyum ≥ %%90",'
                     'IF(%s>=0.6,"ŞARTLI — kontrolör eğitimi / kriter netleştirme",'
                     '"RED — nitelik ölçüm sistemi yetersiz")))'
                     % (G(9), G(9), G(7), G(9)))
        ws.cell(r + 1, 1, "Referans sütununa bilinen doğru sonuç (OK/NOK), A/B/C sütunlarına her "
                          "kontrolörün iki bağımsız değerlendirmesi girilir. Parçaların ~yarısı "
                          "sınır numune olmalı. Kabul: Kappa ≥ 0,75 — AIAG MSA 4. Baskı Bölüm III-C."
                ).font = Font(size=8, italic=True, color="808080")
        ws.merge_cells(start_row=r + 1, start_column=1, end_row=r + 1, end_column=9)
        ws.page_setup.orientation = "portrait"

    wb.save(hedef)
    return len(hepsi)


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

    # APQP bölüm özeti (Program Metrikleri için) — adım listesi apqp.html'deki
    # FR91 verisinden okunur, tek kaynak orası.
    v["apqp_bolumler"] = apqp_bolum_ozeti(v)
    return v


def apqp_bolum_ozeti(v):
    """apqp.html içindeki FR91 listesinden bölüm/adım sayıları; kanıtı ERP'den
    gelen adımlar 'tamamlanan' sayılır."""
    try:
        h = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "apqp.html"),
                    encoding="utf-8").read()
        m = re.search(r"const FR91 = (\[.*?\]);", h, re.S)
        bolumler = json.loads(m.group(1)) if m else []
    except Exception:
        bolumler = []
    kanit = {"fmea": bool(v.get("fmea_not", "").startswith("P-FMEA mevcut")),
             "plan": True, "opkart": bool(v["rota"]), "akis": True}
    ozet = []
    for b in bolumler:
        tamam = sum(1 for a in b["adimlar"] if a.get("kanit") and kanit.get(a["kanit"]))
        ozet.append({"no": b["no"], "ad": b["ad"], "adim": len(b["adimlar"]), "tamam": tamam})
    return ozet


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
    if n: print("   ✓ FR81 Toplantı Tutanağı            (%d madde — APQP madde no ile eklenir)" % n)

    n = uret("PL11 Onaylı Tedarikçi Listesi %s.xlsx" % kod, pl11, "PL11 Onaylı Tedarikçi Listesi")
    if n:
        print("   ✓ PL11 Onaylı Tedarikçi Listesi     (%d otomotiv tedarikçi, %s)" % (n, v["lokasyon_ad"]))

    if uret("FR228 Ambalaj Standardı Formu %s.docx" % kod, fr228, "FR228 Ambalaj Standardı"):
        print("   ✓ FR228 Ambalaj Standardı Formu     (fotoğraflar kaldırıldı — bu ürüne ait değil)")
    if uret("FR148 Değişiklik Yönetimi Formu %s.xlsx" % kod, fr148, "FR148 Değişiklik Yönetimi"):
        print("   ✓ FR148 Değişiklik Yönetimi Formu   (başlık dolduruldu, risk satırları ekipte)")
    n = uret("FR181 Öğrenilmiş Dersler %s.xlsx" % kod, fr181, "FR181 Öğrenilmiş Dersler")
    if n: print("   ✓ FR181 Öğrenilmiş Dersler          (%d ilgili kayıt işaretlendi)" % n)
    if uret("FR91 APQP-Takip Formu %s.xlsx" % kod, fr91, "FR91 APQP Takip Formu"):
        print("   ✓ FR91 APQP-Takip Formu             (77 adım, ürün başlığıyla)")
    n = uret("APQP Program Metrikleri %s.xlsx" % kod, program_metrikleri, "APQP Program Metrikleri")
    if n: print("   ✓ APQP Program Metrikleri           (%d bölüm, kırmızı/sarı/yeşil)" % n)

    n = uret("PL41 Kontrol Planı %s.xlsx" % kod, pl41_kontrol_plani, "PL41 Kontrol Planı")
    if n: print("   ✓ PL41 Kontrol Planı                (%d karakteristik, Leansys verisi)" % n)
    n = uret("FR34 P-FMEA %s.xlsx" % kod, fr34_pfmea, "FR34 P-FMEA")
    if n: print("   ✓ FR34 P-FMEA (Excel çıktısı)       (%d satır, AIAG-VDA 30 sütun)" % n)
    else: print("   ! FR34 P-FMEA                       PFMEA modülünde bu ürünün projesi yok")
    n = uret("MSA Planı %s.xlsx" % kod, msa_plani, "MSA Planı")
    if n: print("   ✓ MSA Planı                         (%d ölçüm aleti)" % n)
    n = uret("FR86 Gage R&R %s.xlsx" % kod, fr86_gage_rr, "FR86 Gage R&R")
    if n: print("   ✓ FR86 Gage R&R                     (%d alet, formüller canlı — ölçüm girilecek)" % n)

    ppap_belgeleri(v, klasor, uret)

    n = uret("Kapasite Takip Formu %s.xlsx" % kod, kapasite, "Kapasite Takip Formu")
    if n: print("   ✓ Kapasite Takip Formu             (%d operasyon, darboğaz: %s / %s adet)"
                % (n, v["darbogaz"]["makine"][:26], v["darbogaz"]["kap"]))


if __name__ == "__main__":
    main()
