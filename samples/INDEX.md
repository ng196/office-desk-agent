# samples/ index (downloaded 24 Oct 2026, box time IST)
Fonts checked with `pdffonts`; text checked with `pdftotext`. "Text layer" = what a copy/paste or indexer gets.

| File | What it is | Lang | Fonts (pdffonts) | Text layer | Reuse |
|---|---|---|---|---|---|
| gazette_india_2026_272395.pdf | Gazette of India weekly, 9 May 2026, 119 pp | Hi+En | KrutiDev010Bold, Vivek, Mangal, ArialUnicodeMS, Times | Hindi header is legacy-encoded: `jftLVªh la-`, `lkIrkfgd@WEEKLY` | Gazette: Copyright Act s.52(1)(q)(i) |
| gazette_india_2025_263348.pdf | Gazette of India weekly, 24 May 2025, 6 pp | Hi+En | KrutiDev010Bold, Vivek, Mangal | mixed legacy + Unicode on same page | s.52(1)(q)(i) |
| gazette_india_2018_184457.pdf | Gazette of India weekly, 31 Mar–6 Apr 2018, 55 pp | Hi+En | only obfuscated names (TT20Et00, TT7E0t00…) | Kruti-style: `çkf/kdkj ls çdkf'kr` = प्राधिकार से प्रकाशित | s.52(1)(q)(i) |
| godl_gazette_2017.pdf | Gazette notification of GODL-India, 13 Feb 2017 | Hi+En | Chanakya, Devnagari-ChanakyaNormalA, Utsaah | Chanakya-encoded: `izkf/dkj ls izdkf'kr` (differs from Kruti!) | s.52(1)(q)(i); also the GODL text itself |
| raj_pwd_tender_140.pdf | Rajasthan PWD tender notice, 29-09-2026 | Hi | KrutiDev010Bold, KrutiDev011, DevLys-010 | `dk;kZy;` = कार्यालय, `fnukad` = दिनांक | Public notice; reuse unclear (state site) — internal test only |
| raj_pwd_tender_38.pdf | Rajasthan PWD tender notice, 2026 | Hi | font names stripped (CIDFont+F1…F10) | Kruti-encoded, but name-based detection FAILS | as above |
| rajbhasha_unicode_circular_2017.pdf | MHA Rajbhasha circular 12015/13/2011-रा.भा.(तक) dated 17 Feb 2012: use Unicode only | Hi | ArialUnicodeMS (Unicode) | Unicode but broken matras: `सविि` for सचिव | Govt circular; public record |
| csmop_2022_hi.pdf | CSMOP 16th ed. 2022, Hindi (school-site mirror; official on darpg.gov.in was 403) | Hi | Mangal | Unicode font, but text layer garbled: `भॉभनटरयॊ ग प्रणारी` | Govt manual; public record; mirror copy — re-fetch from DARPG before shipping |
| csmop_2022_en.pdf | CSMOP 16th ed. 2022, English (darpg.gov.in static upload) | En | Calibri, Arial, Bookman | clean, except scanned forwarding pages (p.3 garbage) | public record |
| cpgrams_comprehensive_guidelines.pdf | DARPG OM S-15/21/2021-(PG), 23 Aug 2024, grievance guidelines | En(+Hi) | Mangal, Liberation | clean | public record |
| ccs_pension_rules_2021_en.pdf | CCS (Pension) Rules 2021, G.S.R. 868(E), 20 Dec 2021 | En | unnamed CID fonts | clean | Gazette: s.52(1)(q)(i) |
| ccs_leave_rules_1972.pdf | CCS (Leave) Rules 1972, consolidated (mirror lgbrimh.gov.in) | En | Cambria, Palatino | clean | rules text; public record |
| rti_act_2005_en.pdf | RTI Act 2005 (cic.gov.in) | En | Times | clean | Act: s.52(1)(q)(ii) needs commentary alongside; fine for internal index |
| prashasnik_shabdavali_en_hi.pdf | Glossary of Administrative Terms En-Hi (lpai.gov.in, 2024 upload), 594 pp, 17 MB | En+Hi | HiddenHorzOCR (scanned) | Hindi OCR layer is junk: `ibttf.:tcfi ~` — needs re-OCR | Govt publication; reuse unclear. Online version: shabd.education.gov.in |
| cic_2014_omprakash_missing_file.pdf | CIC order CIC/DS/A/2013/001788-SA (mirror righttoinformation.wiki) | En | Liberation, Nimbus | clean | quasi-judicial order: s.52(1)(q)(iv) |
| jharkhand_hc_2026_santlal_pension_contempt.pdf | Jharkhand HC Cont. Case (Civil) 403/2025, 20.03.2026 (via livelaw) | En | — | clean | judgment: s.52(1)(q)(iv) |
| cic_2017_jafa_v_mosje.txt / cic_2024_devender_v_cbse.txt / delhihc_2025_kalusingh_wrong_provision.txt | Indian Kanoon page text (HTML stripped) | En | — | — | judgments: s.52(1)(q)(iv); Indian Kanoon page layout is theirs |

Not downloaded: RFRI/ICFRE Unicode circular 2026 (TLS fails from box; read via WebFetch), CAG Report 26/2017 ch.3 (TLS fails; NOT read), Rajbhasha "saral shabdavali" (URL now 404).
