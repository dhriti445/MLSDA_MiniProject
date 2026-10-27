Put the official, free CBIC/DGFT documents here (Customs Tariff GRI, Chapters 73 and 96 with Section XV / chapter notes, DGFT export policy schedule).
Text-layer PDFs are parsed by `ecs/ingest.py:parse_pdf` (one chunk per 4-digit heading and per Note). Review the parsed chunks (`data/index.json`) for your PDFs - layouts vary.
`seed/seed_corpus.txt` is a SMALL PARAPHRASED PLACEHOLDER so the system runs offline; policy values in it are unverified. Delete it once the real corpus is in.
At Evaluation 1, show the passages the 4.1 case depends on: H9617, GRI_1, NOTE_S15_1 (Section XV exclusion of Chapter 96 articles), POL_9617.
