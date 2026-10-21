# Research context: Office Desk Agent

A self-contained brief. Give this whole file to a person or an AI research tool to research anything about this product.

How to read it:
- Facts come from public-source desk research done on 20 Oct 2026. They were **not re-checked** when this file was written. Re-verify anything before relying on it.
- **[Unverified]** = could not be confirmed from the primary source.
- **[Inference]** = an opinion or reading, not a stated fact.
- Where no figure is known, none is given. Do not fill gaps with guesses.

---

## 1. Product in one paragraph
Office Desk Agent is an offline AI helper for a clerk ("dealing hand") in an Indian government, PSU, port, defence or district office. The clerk drops in an incoming letter. The tool summarises it, finds the closest past letters and rules from the office's own files, and drafts a reply in Hindi or English where every line cites the file or rule it came from. The clerk edits and presses Approve, and the reply is saved to an Outbox. It runs fully offline on the office's existing CPU-only PCs, blocks any attempt to send files out, and writes every step to an audit log the boss can read.

Current status: a clickable UI mockup with fake data (`mockup/index.html`, live preview https://office-desk-mockup.vercel.app). No backend yet.

## 2. Target users and their daily work
**Primary user:** a clerk / section assistant / dealing hand who handles incoming mail ("dak") and drafts replies.
**Secondary user:** the section officer or boss, who approves replies and reads the log.

**Typical letters:** RTI applications, pension cases, public complaints and grievances, gate passes, references from senior offices (MP, state, PMO references), circulars and office orders.

**How the work is done today** (per the Central Secretariat Manual of Office Procedure, CSMOP 2022):
1. Dak is received, checked, date-stamped and **diarised** (logged with a diary number in a register).
2. It is marked to the dealing hand, who opens or links a file.
3. The dealing hand writes a **noting** (internal note) and puts up a **draft reply** through the channel of submission.
4. The reply is issued after approval.
Sources: https://moef.gov.in/uploads/2017/09/CSMOP-2022-Sixteenth-Edition.pdf · https://www.darpg.gov.in/static/uploads/2025/10/e4360b9fcbc0a1a94649c758541051a0.pdf

**In e-Office** (NIC's government file system) the same steps are digital: scan → enter metadata → system issues a diary number → e-File → note, draft, approve → sign with DSC/eSign → dispatch. https://www.nic.gov.in/project/eoffice/

**Grievance replies** are "Action Taken Reports" (ATRs): reasoned replies with the documents relied on attached. https://pgportal.gov.in/

**Where the time goes:** a JNPA team member wrote that a complete e-Office file "runs to several hundred pages… Finding the one paragraph that matters used to take hours." https://www.linkedin.com/posts/ca-karan-malhotra_eoffice-aiautomation-aitraining-activity-7505232951501025280-bDrf

**Languages:** Hindi and English (noting and drafting in both is normal in central offices and Hindi-belt states).

## 3. MVP and non-goals
**MVP (5 steps):**
1. Inbox: drop a letter (PDF or text).
2. Summary plus the closest past letters and rules from the office's own files.
3. Hindi or English draft reply; every line cites its source.
4. Clerk edits; Approve saves to Outbox.
5. Fully offline, CPU only, no cloud AI; sending files out is blocked; every step goes to an audit log the boss can read.

**Not in MVP:** Excel register, email sending, handwriting recognition, multiple users, approval chains, voice, languages other than Hindi/English, e-Office integration.

## 4. Hard constraints
- **Air-gapped:** works with no internet at all.
- **CPU only:** no GPU.
- **Local models only:** no cloud AI, no external AI APIs.
- **Data never leaves the office.** Outbound file transfer is blocked by the tool.
- **Existing hardware:** must run on PCs the office already owns.
- **Human in charge:** nothing is issued without a person pressing Approve.

## 5. Key differentiators
1. **Line-by-line citations** to the office's own past files, orders and rules.
2. **Human Approve step** before anything is saved as final.
3. **Audit log** of every step, readable by the boss.
4. **Outbound block:** trying to send a file out is refused and logged.
5. **Runs on existing hardware**, offline, CPU only.
6. **Sits beside e-Office with no integration:** the clerk exports or copies the letter in and pastes the approved reply back. No dependence on e-Office APIs.

## 6. Market and buyers
**[Inference] Who to target first:**
1. **PSUs, ports, defence and other sensitive establishments** that run their own systems and don't allow external AI.
2. **District collectorates and tehsils** recently moved onto e-Office: high letter volume, little budget for per-seat software, existing desktops.
3. (Possible) court/tribunal registries and information commissions: confidential work, replies drafted from precedent.

**Not a first target: central ministries.** They are nearly fully on e-Office (93.62% e-Files, 95.19% e-Receipts as of 31 Oct 2025; https://www.pib.gov.in/PressReleseDetailm.aspx?PRID=2203218) and are being covered by NIC tools and NextGen CPGRAMS.

**Volume signals:**
| Metric | Figure | Source |
|---|---|---|
| CPGRAMS grievances received | 2024: 26.2 lakh; 2025: 22.8 lakh | https://www.pib.gov.in/PressReleasePage.aspx?PRID=2241740&lang=1&reg=3 |
| Central grievance disposal time | Avg 15 days in 2025 (22 in 2022) | same as above |
| RTI applications to central public authorities, 2024-25 | 17.95 lakh | https://thesecretariat.in/article/digitisation-of-rti-framework-drives-twofold-increase-in-applications-over-a-decade |
| RTI appeals pending in information commissions | 4,13,972 on 30 Jun 2025 | https://www.snsindia.org/wp-content/uploads/2025/10/Press-Release-2025.pdf |
| Special Campaign 5.0 (Oct 2025) | 29.52 lakh files closed or weeded | https://www.pib.gov.in/PressReleseDetailm.aspx?PRID=2209849&lang=1&reg=1 |

No published per-clerk daily letter volumes were found.

**States and districts switching to e-Office by order:** Chhattisgarh (no physical files after 31 Dec 2025), Bhopal collectorate (from 1 May 2025), Andhra Pradesh district offices (Sep 2026), Haryana statewide (Aug 2026). Sources: https://npg.news/chhattisgarh/cg-good-governance-31-december-ke-bad-chhattisgarh-mein-physical-files-and-notesheet-par-purnt-1301335 · https://www.freepressjournal.in/bhopal/e-office-execution-at-bhopals-collector-office-from-may-1 · https://www.telugu360.com/no-more-physical-files-in-ap-govt-offices-within-a-month/ · https://timesofindia.indiatimes.com/city/chandigarh/haryana-makes-e-office-mandatory-across-all-govt-departments/articleshow/132871708.cms

## 7. Comparables and competitors
| Player | What it does | Deployment | Relevance |
|---|---|---|---|
| **JNPA "Nirikshak"** (custom build) | Reads a whole e-Office file, lists pending observations, drafts a noting where every claim cites a page or rule; officer approves; nothing goes into e-Office automatically. Team said running fully on JNPA infrastructure "is why it got deployed at all." Deployed Sep 2026. | On-prem | **Proof of demand** and of the on-prem requirement. A one-off build, not a product. Source is a LinkedIn post **[Unverified beyond that post]**. https://www.linkedin.com/posts/ca-karan-malhotra_eoffice-aiautomation-aitraining-activity-7505232951501025280-bDrf |
| **Sarvam "Indus"** | Drafting and file-noting help, RTI response generation, OCR in Indian scripts, 22 languages, e-Office integration "wherever API access is available". Maharashtra: ~2,500 users, ₹1,200/user/month launch price (list ₹2,500), ₹11.26 cr over 2 years. UP Chief Secretary directed departments to use it (Sep 2026). | Hosted, per seat ("secure and audited infrastructure within India"). **On-prem option [Unverified]** | **Main competitor.** Gaps vs us: per-seat price, hosted rather than on the desk, depends on e-Office APIs. https://www.cnbctv18.com/technology/maharashtra-clears-%e2%82%b911-26-cr-sarvam-ai-deployment-for-govt-departments-19964253.htm · https://www.sarvam.ai/indus-cowork |
| NIC e-Office 7.x | Diarising, e-File, noting/drafting editor, knowledge-management search, Bhashini dictation and translation | Government-hosted | No AI drafting advertised. Could add it later (risk). https://www.nic.gov.in/project/eoffice/ |
| NextGen CPGRAMS (planned) | AI-suggested resolutions and auto-filled ATRs from similar past grievances | Government | Covers generic grievance replies; avoid competing there. https://www.darpg.gov.in/static/uploads/2025/11/031f6cdcc93bb39a667c7c824d5d757c.pdf |
| CPGRAMS IGMS 2.0 (IIT Kanpur) | Grievance triage and analytics | Government | Analytics only, no drafting |
| CoRover / BharatGPT (MeitY agentic platform, Oct 2026) | Citizen-facing agents, starting with DigiLocker | SaaS and on-prem | Citizen services, not the clerk's desk |
| Kerala (Chief Secretary order, Jul 2026) | AI to draft file notes, retrieve past GOs, summarise, translate; tool not yet chosen | — | Open evaluation; possible entry point |
| Andhra Pradesh Legal AI Assistant tender | Runs on Google Cloud | Cloud | Shows some states accept cloud |
| Bhashini / Kanthasth 2.0 | Government translation | Government | Translation, not drafting |
| UK "Humphrey" (Redbox, Minute) | Redbox trial: 89% of 282 users saved time, median 2 h/week | Government-built | Benchmark for time-saved claims |
| Singapore "Pair" | Government LLM for writing, handles Restricted/Sensitive data; ~80% of 150K officers have used it | Government-hosted | Shows a national standard tool wins once it exists |

Not checked: Gnani.ai government work; Andhra Pradesh RTGS drafting tools.

## 8. Relevant policy and procurement
- **Finance Ministry advisory, 29 Jan 2025** (Dept of Expenditure): employees should avoid AI tools such as ChatGPT and DeepSeek on office computers and devices, citing confidentiality of government data. https://www.reuters.com/technology/artificial-intelligence/indias-finance-ministry-asks-employees-avoid-ai-tools-like-chatgpt-deepseek-2025-02-05/
- **DPIIT procurement-AI RFP on GeM** (10 Sep 2026, about ₹12.5 cr, QCBS). Reported wording: "on-premises LLM stack… no external AI APIs"; drafts must be "editable, source-cited, confidence-scored, and explicitly approved by a human"; AI actions "audit-logged"; module "kill switches". **[Unverified]**: the PDF could not be opened; terms are from a search index. https://bidplus.gem.gov.in/bidding/bid/downloadBuyerDoc/9879428/17891043357327.pdf
- **HAL GeM bid** (28 Aug 2026) for an on-prem AI document management system. **[Unverified]**, same reason. https://bidplus.gem.gov.in/showbidDocument/9816123
- **MeitY India AI Governance Guidelines (Nov 2025):** risk-based, no new law, relies on existing laws and regulators. **[Inference]** There is no blanket on-prem mandate; demand comes from each office's own confidentiality rules.
- **DPDP Act 2023 / DPDP Rules (notified 13 Nov 2025):** most data-fiduciary duties apply from 13 May 2027. https://www.meity.gov.in/documents/act-and-policies/digital-personal-data-protection-rules-2025-gDOxUjMtQWa
- **CERT-In Directions (28 Apr 2022):** report incidents within 6 hours; keep ICT logs for 180 days within India. https://www.cert-in.org.in/PDF/CERT-In_Directions_70B_28.04.2022.pdf
- **Procurement barriers:** buying is via GeM, often QCBS or lowest-bid, with earnest-money deposits and turnover criteria. Government apps need a CERT-In empanelled "safe-to-host" security audit (yearly and after major changes) and may need GIGW/STQC certification. https://guidelines.india.gov.in/security-guidelines-and-attributes/ · https://www.stqc.gov.in/node/1350
- **Staff/union view:** no government-employee union opposition found. Bank unions ask for consultation, human oversight and job-security safeguards before AI rollout.

## 9. Risks and reasons it might not be needed
- e-Office plus NIC/NextGen CPGRAMS may add drafting later and make a separate tool redundant.
- Once a state picks a vendor (e.g. Sarvam), others may be shut out for years.
- Office PCs are locked down by IT; installing an app and a model needs approval. **[Inference]** A small server on the office network may be more realistic than every clerk's PC.
- A wrong fact in an official letter is a disciplinary risk, so citations and human approval are essential.
- Past files are often scanned PDFs or paper; OCR quality in Hindi is a known problem.
- Some states (Kerala, TN, Maharashtra) work in Malayalam, Tamil, Marathi; MVP covers only Hindi/English.
- Some states accept cloud AI, so "offline" is not a must-have everywhere.

## 10. Open technical questions
- **Which local model?** Candidates: Qwen or Llama family models run via llama.cpp (or similar local servers). Which size fits a typical office PC?
- **Hindi quality:** how good are small local models at formal official Hindi (rajbhasha style) drafting and summarising?
- **Retrieval over scanned PDFs:** OCR for Hindi/English scans (Devanagari), chunking, and local embeddings that work for both languages.
- **Citation accuracy:** how to make sure every draft line really comes from the cited source, and flag lines that don't.
- **CPU speed:** measured tokens per second, time to first draft and peak RAM on typical office PCs (no measurements exist yet; must be tested).
- **Typical office hardware:** what CPU/RAM/OS do clerks' PCs actually have? (Unknown.)
- **Indic fonts:** Devanagari rendering in the UI and in saved replies (Unicode vs legacy fonts like Kruti Dev still used in some offices).
- **Outbound block:** how to reliably block network/file egress on Windows without admin rights, and prove it.
- **Audit log:** format, tamper evidence (e.g. hash chain), and what the boss needs to see.
- **Packaging:** single-PC install vs a small LAN server; Windows support.

## 11. Suggested research questions
1. How many letters does a typical clerk in a district collectorate or PSU handle per day, and which types dominate?
2. What do officers actually check before approving a draft reply? What makes them reject one?
3. Which local models (e.g. Qwen, Llama) give the best formal Hindi on CPU, and at what speed on an i5/8–16 GB PC?
4. How well do open OCR tools read scanned Hindi government letters?
5. What hardware and OS do clerks' PCs in PSUs, ports and collectorates typically have?
6. Does Sarvam Indus offer an on-prem or offline edition, and at what price?
7. Who built JNPA's Nirikshak, how is it deployed, and are other ports or PSUs asking for the same?
8. What exactly does the DPIIT GeM RFP say about citations, confidence scores, human approval, logs and kill switches? (Open the PDF.)
9. How do PSUs and district offices buy small software like this: GeM direct purchase, through a system integrator, or another route? What certifications are needed?
10. What e-Office export/import options exist so a clerk can move letters in and replies out without integration?
11. Are there rules on using AI-drafted text in official correspondence (e.g. disclosure, sign-off)?
12. Which fonts and encodings do offices use for Hindi correspondence today?
13. What do RTI, pension and gate-pass replies usually contain, and which rules (RTI Act sections, pension rules) are cited most?
14. Is NIC planning AI drafting in a future e-Office release?
