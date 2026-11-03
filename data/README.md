# NETDEFY Data Directory Structure & Governance

This directory organizes network traffic datasets across processing stages:

- `raw/`: Immutable, original network capture datasets (e.g., CICIDS2017 `MachineLearningCSV.zip` and uncompressed CSV files). Files in this directory are write-protected and strictly excluded from version control via `.gitignore`.
- `interim/`: Intermediate datasets that have undergone validation, deduplication, cleaning, and preliminary feature extraction, but prior to train/validation/test temporal splitting.
- `processed/`: Final, temporally partitioned, scaled feature matrices and labels ready for model training, threshold calibration, and evaluation.

---

## 1. Dataset Acquisition Instructions (CICIDS2017)

The Canadian Institute for Cybersecurity (UNB) requires registration before granting access to the CICIDS2017 dataset. Direct unauthenticated downloads are prohibited (HTTP 403 Forbidden).

### Official Acquisition Steps:
1. Visit the official UNB dataset portal:  
   [https://www.unb.ca/cic/datasets/ids-2017.html](https://www.unb.ca/cic/datasets/ids-2017.html)
2. Open the official registration form:  
   [http://cicresearch.ca/CICDataset/CIC-IDS-2017/](http://cicresearch.ca/CICDataset/CIC-IDS-2017/)
3. Complete the registration form with your Name, Email, Organization, and Country.
4. On the subsequent file listing page, download:
   - `MachineLearningCSV.zip` (~225 MB compressed, ~2.8 GB uncompressed)
5. Place the downloaded archive into this directory:
   `data/raw/MachineLearningCSV.zip`
6. Run the automated acquisition & extraction utility:
   ```bash
   python scripts/acquire_dataset.py
   ```

---

## 2. Dataset Manifest (`data/raw/manifest.json`)

All files placed under `data/raw/` are tracked in `manifest.json`. The manifest records:
- Canonical dataset name and version.
- File sizes, SHA-256 cryptographic hashes, row counts, and column counts.
- Integrity verification results.

To verify or regenerate the manifest:
```bash
python scripts/acquire_dataset.py
```

---

## 3. Forensic Inspection Protocol

Once the raw dataset files are extracted, execute the chunk-based forensic inspector:
```bash
python scripts/inspect_dataset.py --chunk-size 50000
```
This processes all CSV files in memory-bounded chunks suitable for Apple Silicon (8 GB unified memory), generating structured reports in `reports/`:
- `reports/dataset_forensic_summary.md` and `.json`
- `reports/label_distribution.md` and `.csv`
- `reports/temporal_distribution.md` and `.csv`
- `reports/duplicate_investigation.md`
- `reports/feature_schema.md`

---

## 4. Data Governance & Integrity Rules

1. **Strict Immutability:** Never modify, reformat, or overwrite files in `data/raw/`.
2. **No Git Tracking:** Never commit raw or processed datasets or zip archives to Git.
3. **Reproducibility:** Every downstream interim and processed artifact must document its source lineage, processing timestamp, and SHA-256 manifest hash.
