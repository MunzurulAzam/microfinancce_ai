"""
ask_ai — Natural-language Q&A over the DW data warehouse.

DW is a single MSSQL catalog holding all 4 countries (UG/KY/ZM/TZ); every table
carries CountryId + CountryCode, so one connection answers both single-country
and cross-country questions.

  - db.py     : pooled MSSQL access, dry-run validation, guarded execution
  - prompt.py : question -> prompt (cached schema + glossary + few-shot)
  - engine.py : question -> SQL (local Ollama) -> DW -> answer
  - api.py    : Flask blueprint `POST /api/ask-ai`

The model only ever writes SQL — every number in an answer comes from DW.
"""
