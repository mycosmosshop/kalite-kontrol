# -*- coding: utf-8 -*-
# apqp.html icindeki APQP adim listesini FR91 SABLONUNDAN yeniden uretir.
# Liste elle yazilmaz; sablon revize olursa bu betik calistirilir:
#   python apqp_adimlari_tazele.py "C:\...\FR91 APQP-Takip Formu ....xlsx"
#
# FR91 sutun duzeni:
#   B madde no | E aciklama (E:S) | T AIAG ref | X sorumluluk | Z prosedur
#   AA form | AB bitis | AE tamamlanma | AI durum
import sys, json, io, re, openpyxl

VARSAYILAN = r"C:\Users\User\Desktop\APQP 36.72010-6345\FR91 APQP-Takip Formu 36.72010-6345.xlsx"
HEDEF = "apqp.html"


# ── AIAG APQP 3rd Edition (Mart 2024) eksikleri ──────────────────────────
# FR91'de karşılığı olmayan, standardın numaralı maddeleri. Yalnız Sanifoam'da
# uygulanabilir olanlar alındı: tasarım sorumluluğu müşteride olduğu için
# DFMEA/tasarım doğrulama maddeleri (2.1–2.4) ve gömülü yazılım maddeleri
# eklenmedi. Her madde standarttaki numarasını taşır.
EK_ADIMLAR = {
    "2": [
        ("Proje kapsamı ve APQP ekibi tanımlandı (roller, yetkiler, toplantı düzeni)",
         "0.1; 0.2", "Proje Ekibi", "", "FR81 Toplantı Tutanağı"),
        ("Tedarikçi seçimi ve onayı tamamlandı — sourcing kontrol listesi",
         "0.5", "Satınalma", "", "PL11 Onaylı Tedarikçi Listesi"),
        ("Açık konu (concern) matrisi oluşturuldu; sorumlu ve termin atandı",
         "0.9", "Proje Ekibi", "", "FR81 Toplantı Tutanağı"),
        ("Risk değerlendirme ve azaltma planı hazırlandı (REMS)",
         "1.17", "Proje Ekibi Kalite", "", "Risk Değerlendirme Planı"),
        ("Değişiklik yönetimi başlatıldı — her APQP çıktısında değişiklik günlüğü "
         "(neden, talep eden, onaylayan, tarih)",
         "1.15", "Kalite", "", "Değişiklik Günlüğü"),
        ("APQP program metrikleri hazırlandı ve yönetime sunuldu "
         "(kırmızı/sarı/yeşil durum, kapı onayı)",
         "1.16; 1.14", "Proje Yöneticisi", "", "APQP Program Metrikleri"),
    ],
    "3": [
        ("Ürün/proses kalite sistemi gözden geçirmesi yapıldı",
         "3.2", "Kalite", "", "FR81 Toplantı Tutanağı"),
        ("Yerleşim planı (floor plan layout) hazırlandı — malzeme akışı, kontrol "
         "noktaları, ara stok alanları",
         "3.4", "Üretim", "", "Yerleşim Planı"),
    ],
    "5": [
        ("Safe Launch / güçlendirilmiş kontrol dönemi planlandı ve uygulandı "
         "(seri üretim başlangıcında ilave muhafaza)",
         "4.7", "Kalite Üretim", "", "Leansys Kontrol Planı"),
        ("Faz çıkış onayı alındı — yönetim desteği / kapı gözden geçirmesi",
         "4.8; Ek B", "Proje Yöneticisi", "", "FR91 APQP Takip Formu"),
    ],
    "8": [
        ("Varyasyonun azaltılması — proses yeterliliği izlemeye alındı, "
         "iyileştirme planı yapıldı",
         "5.1", "Kalite", "", "FR88 Süreç Yeterlilik Ölçümü Formu"),
        ("Müşteri memnuniyeti izleniyor (şikâyet, PPM, skorkart)",
         "5.2", "Kalite Satış", "", "PPM Takip FR100 KPI"),
        ("Müşteri hizmeti ve teslimat performansı izleniyor (termin, eksik/fazla)",
         "5.3", "Lojistik", "", "PPM Takip FR100 KPI"),
        ("Öğrenilmiş dersler kaydedildi ve benzer ürünlere aktarıldı "
         "(TGR/TGW, hataya dayanıklı çözümlerin kalıcı kaydı)",
         "5.4", "Kalite", "", "FR181 Öğrenilmiş Dersler"),
    ],
}
EK_BOLUM = {"8": "Geri Besleme, Değerlendirme ve Düzeltici Faaliyet"}


def ek_adimlari_uygula(bolumler):
    """AIAG 3rd Ed. eksiklerini ilgili bölümlerin sonuna ekler."""
    var = {b["no"]: b for b in bolumler}
    for bno, maddeler in EK_ADIMLAR.items():
        b = var.get(bno)
        if not b:
            b = {"no": bno, "ad": EK_BOLUM.get(bno, "Ek"), "adimlar": []}
            bolumler.append(b)
            var[bno] = b
        mevcut = len(b["adimlar"])
        for i, (ad, aiag, sorumluluk, prosedur, form) in enumerate(maddeler):
            adim = {"no": "%s.%d" % (bno, mevcut + i + 1), "ad": ad, "aiag": aiag,
                    "sorumluluk": sorumluluk, "prosedur": prosedur, "form": form,
                    "aiag3": True}
            f = form.lower()
            for anahtar, kanit in (("fmea", "fmea"), ("kontrol plan", "plan"),
                                   ("operasyon kart", "opkart"),
                                   ("akış diyagram", "akis")):
                if anahtar in f:
                    adim["kanit"] = kanit
                    break
            b["adimlar"].append(adim)
    return bolumler


def cikar(sablon):
    wb = openpyxl.load_workbook(sablon, data_only=True)
    ws = wb[wb.sheetnames[0]]

    def h(r, c):
        v = ws.cell(r, c).value
        return "" if v is None else str(v).strip()

    bolumler, bolum = [], None
    for r in range(1, ws.max_row + 1):
        no, ad = h(r, 2), h(r, 5)
        if not no and not ad:
            continue
        if re.fullmatch(r"\d+", no):            # bolum basligi
            bolum = {"no": no, "ad": ad, "adimlar": []}
            bolumler.append(bolum)
            continue
        if not bolum:
            continue
        # Excel 2.10'u sayi olarak saklayip 2.1 gosteriyor; bolum icinde
        # tekrar eden numara .10 demektir (satir sirasi esastir).
        if no in [x["no"] for x in bolum["adimlar"]]:
            no += "0"
        adim = {"no": no, "ad": ad, "aiag": h(r, 20), "sorumluluk": h(r, 24),
                "prosedur": h(r, 26), "form": h(r, 27)}
        # ERP'de karsiligi olan adimlar otomatik isaretlenir
        f = adim["form"].lower()
        for anahtar, kanit in (("fmea", "fmea"), ("kontrol plan", "plan"),
                               ("operasyon kart", "opkart"),
                               ("akış diyagram", "akis"), ("akis diyagram", "akis")):
            if anahtar in f:
                adim["kanit"] = kanit
                break
        bolum["adimlar"].append(adim)
    return bolumler


def main():
    sablon = sys.argv[1] if len(sys.argv) > 1 else VARSAYILAN
    bolumler = ek_adimlari_uygula(cikar(sablon))
    toplam = sum(len(b["adimlar"]) for b in bolumler)
    if not toplam:
        raise SystemExit("Şablondan adım çıkarılamadı: " + sablon)

    s = io.open(HEDEF, encoding="utf-8").read()
    yeni = "const FR91 = " + json.dumps(bolumler, ensure_ascii=False, separators=(",", ":")) + ";"
    s, n = re.subn(r"const FR91 = \[.*?\];", lambda m: yeni, s, count=1, flags=re.S)
    if n != 1:
        raise SystemExit("apqp.html içinde FR91 listesi bulunamadı")
    io.open(HEDEF, "w", encoding="utf-8").write(s)

    print("%s → %d bölüm / %d adım" % (HEDEF, len(bolumler), toplam))
    for b in bolumler:
        print("   %-3s %-50s %2d adım" % (b["no"], b["ad"][:50], len(b["adimlar"])))
    kanitli = sum(1 for b in bolumler for a in b["adimlar"] if a.get("kanit"))
    ek = sum(1 for b in bolumler for a in b["adimlar"] if a.get("aiag3"))
    print("   ERP'den otomatik işaretlenebilen: %d adım" % kanitli)
    print("   AIAG APQP 3rd Ed. (Mart 2024) ile eklenen: %d adım" % ek)


if __name__ == "__main__":
    main()
