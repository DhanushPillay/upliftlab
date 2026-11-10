# Data

This document records where the data comes from, how it is verified, what the columns mean, and what each license allows. No raw data is committed to the repository.

## 1. Data policy

- Raw files live in `data/raw/` and are ignored by Git.
- Every download is verified against a known checksum.
- A checksum mismatch stops the run. It is not a warning.
- Processed files live in `data/processed/` and are also ignored.
- The loader never modifies the raw file.
- Dataset licenses are respected. The Criteo data is non-commercial.

## 2. Hillstrom e-mail dataset

### Source

- Original publication: Kevin Hillstrom, MineThatData, March 2008.
- Download: `https://hillstorm1.s3.us-east-2.amazonaws.com/hillstorm_no_indices.csv.gz`
- Compressed size: 443,070 bytes

The bucket name contains the spelling "hillstorm". That is the actual URL, not a typo in this document. Checksums are in the single table in section 6.

### What it contains

64,000 customers who purchased within the previous twelve months. The customers were randomized into three roughly equal e-mail arms:

- Mens E-mail
- Womens E-mail
- No E-mail

Columns:

| Column | Meaning |
| --- | --- |
| `recency` | Months since the last purchase |
| `history_segment` | Bucketed past spend |
| `history` | Past twelve-month spend |
| `mens` | Bought mens merchandise |
| `womens` | Bought womens merchandise |
| `zip_code` | Urban, suburban, or rural (the file uses the upstream spelling `Surburban`) |
| `newbie` | New customer flag |
| `channel` | Purchase channel |
| `segment` | Treatment arm |
| `visit` | Visited the website in the following two weeks |
| `conversion` | Purchased in the following two weeks |
| `spend` | Dollars spent in the following two weeks |

### Use in this project

- Primary case study.
- Primary contrast: any e-mail versus no e-mail.
- Secondary contrast: Mens E-mail versus Womens E-mail (planned; not in the Phase 1 report).
- Primary outcome: `visit`.
- Secondary outcomes: `conversion`, `spend`.
- CUPED covariate: `history`, measured before the campaign.
- Uplift covariates: all pre-treatment columns except `segment`, `visit`, `conversion`, and `spend` (planned for Phase 2).

### License

No formal open license is stated at the source, so no explicit permission to redistribute is granted. Cite Kevin Hillstrom and MineThatData, and do not redistribute the raw file in this repository.

## 3. Criteo Uplift dataset

### Source

- Criteo Research, Uplift Modeling v2.1 (2018).
- Dataset page: `https://ailab.criteo.com/criteo-uplift-prediction-dataset/`
- Stable mirror: `https://huggingface.co/datasets/criteo/criteo-uplift/resolve/main/criteo-research-uplift-v2.1.csv.gz`
- Compressed size: 311,422,618 bytes
- Uncompressed size: approximately 3.2 GB

The original v1 release had 25,309,483 rows. Criteo later found a leak: the incrementality level was not uniform across advertisers, and the features revealed the advertiser. The v2.1 release fixes this. This project uses v2.1 only.

### What it contains

13,979,592 rows from randomized ad incrementality tests. Columns:

| Column | Meaning |
| --- | --- |
| `f0` to `f11` | Anonymized pre-treatment features |
| `treatment` | Randomized treatment assignment |
| `exposure` | Whether the user was actually exposed to the ad |
| `visit` | Visit outcome |
| `conversion` | Conversion outcome |

Key figures for v2.1:

- Average visit rate: 4.6992%
- Average conversion rate: 0.292%
- Treatment ratio: 0.85

The treatment and control groups are unbalanced by design. The exact ratio is computed from the file and reported, not assumed.

### Use in this project

- Scale case study (planned).
- Routine runs use a deterministic 10% sample. The full file is an optional scale run.
- The sample rule is fixed in the loader: assign each row an integer id from 0 to N-1, compute a 32-bit multiplicative hash, and keep rows where `hash % 10 == 0`. It is reproducible for a fixed file, but it is **order-dependent**: reordering or concatenating the rows changes which rows receive which id.
- Primary treatment: `treatment`.
- `exposure` is post-treatment and is not used as a covariate or as the main treatment variable.
- Primary outcome: `visit`. Secondary: `conversion`.
- Features: 12 anonymized columns, `f0` through `f11`.

### License

CC BY-NC-SA 4.0. Non-commercial use only. Share-alike applies to derived data, including aggregate tables, plots, and trained models. Cite:

> Diemert, Betlei, Renaudin, Amini (2018). A Large Scale Benchmark for Uplift Modeling. AdKDD.

The project uses the data for non-commercial research and portfolio analysis. Anyone using this repository commercially must check the license independently.

## 4. Optional datasets

These are not part of the first benchmark. They are documented because the loader interface should be able to accept them later.

| Dataset | Source | Why it is optional |
| --- | --- | --- |
| Cookie Cats | Mobile game A/B test, 90,189 players | Simple readout only; no pre-period covariate for CUPED |
| Lenta | scikit-uplift dataset | Different domain; useful robustness check |
| X5 RetailHero | scikit-uplift dataset | Multi-table; more preprocessing |
| MegaFon | scikit-uplift dataset | Anonymized features; useful external check |

These datasets are not downloaded by default and their mirrors are not part of the reproducibility contract yet.

## 5. Preprocessing conventions

### Treatment encoding

- Hillstrom: `treatment = 1` for Mens E-mail or Womens E-mail, `0` for No E-mail. The original `segment` column is kept for secondary contrasts.
- Criteo: `treatment` is already binary.

### Outcomes

- Binary outcomes stay 0/1.
- `spend` stays in dollars.
- The primary outcome is fixed per dataset before modeling.

### Covariates

- Only pre-treatment columns are used.
- Identifiers and post-treatment columns are dropped.
- Categorical columns are expanded to observed dummy levels; the SMD rows are named, so dummy ordering does not affect the result.
- Missing values are rejected by the readout rather than imputed.
- `history` is used raw for CUPED and for tree models. A log transform is a documented option, not a hidden default.

### Splits

- 60% train, 20% validation, 20% holdout.
- Stratified by treatment and outcome.
- The holdout is created once and reused for every model and baseline.
- The uplift model never sees holdout outcomes during training or model selection.

### Leakage checks

- No outcome-derived features.
- No `exposure` in Criteo.
- No post-treatment variables.
- No target encoding fitted on the holdout.
- The CUPED covariate is checked to be pre-treatment.

## 6. Checksum table

The loader pins and verifies SHA-256. The MD5 column is kept only as an upstream cross-check with the scikit-uplift mirrors.

| Dataset | File | SHA256 (enforced) | MD5 (upstream cross-check) |
| --- | --- | --- | --- |
| Hillstrom | `hillstorm_no_indices.csv.gz` | `bab6578f60db5d792f1c2372c502f029152a5249cf5ea84390f3b7f885d7234f` | `a68a81291f53a14f4e29002629803ba3` |
| Criteo v2.1 | `criteo-research-uplift-v2.1.csv.gz` | `2716e1bf0fd157a93b5bf86924d9088419dfbac2022c6cd90030220634f616dc` | not published |

## 7. Reproducibility

- Downloads are cached and verified against SHA-256 when fetched and again before analysis.
- The checksum is part of the dataset config, not a comment in code.
- A failed checksum raises an error with the expected and actual values.
- The readout JSON records the dataset name, SHA-256, and row count.
- The simulation JSON records the seed, alpha, replications, package versions, and platform.
