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
    bolumler = cikar(sablon)
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
    print("   ERP'den otomatik işaretlenebilen: %d adım" % kanitli)


if __name__ == "__main__":
    main()
