# Office Desk Agent (working name)

> **Hosting note:** the public preview at https://office-desk-mockup.vercel.app is the static UI mockup only (fake data, no backend).
> The live engine (FastAPI: Inbox -> summary + past files -> draft -> Approve) runs locally on the CPU of the office machine.
> It cannot run on Vercel serverless (long-running Python, local models, persistent disk). See CORE.md to run it.

An offline AI helper for the clerk's desk in a government, PSU, port, defence or district office.

## The problem
Clerks spend hours on routine letters: RTI requests, pension cases, complaints, gate passes, references from senior offices. Each one means finding the right past file or rule and writing a proper reply in Hindi or English. Cloud AI tools like ChatGPT are not allowed on office computers, and office data must not leave the building. So today the clerk does it all by hand.

## MVP (only this)
1. **Inbox:** drop an incoming letter (PDF or text) into the Inbox.
2. **Summary + past files:** it shows a short summary and the closest past letters and rules from the office's own files.
3. **Draft:** it drafts an official reply in Hindi or English. Every line points to the past file or rule it came from.
4. **Approve:** the clerk edits the draft and presses Approve. The reply is saved to Outbox. Nothing goes out without a person approving it.
5. **Offline and logged:** everything runs on this computer with no internet, on the CPU only, with no cloud AI. Trying to send a file out is blocked, and every step is written to a log the boss can read.

## Not in MVP
Excel register, sending email, handwriting, multiple users, approval chains, voice, other languages, e-Office integration.

## Constraints
- CPU only, no GPU.
- No internet. No cloud AI. Data never leaves the office.
- Runs on the PCs the office already has.
- Sits beside e-Office. The clerk copies files in and pastes the approved reply back. No integration needed.

## Status
- Engine: Python/FastAPI app in `desk/` (run locally, see CORE.md).
- Mockup: static UI with fake data.
- Mockup: `mockup/index.html` (open it in any browser).
- Mockup preview (UI only): https://office-desk-mockup.vercel.app

## Folder layout
```
README.md             this file
research-context.md   self-contained brief for researching the product
mockup/index.html     clickable UI mockup (single HTML file, fake data)
docs/                 notes and design docs (empty for now)
```

## Third-party notices
See THIRD_PARTY_NOTICES.md for dependency and model licences. No project LICENSE file.


`Dockerfile` and `fly.toml` are NOT used (Fly.io hosting was dropped); kept for reference only.
