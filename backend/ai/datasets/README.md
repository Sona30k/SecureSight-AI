# Synthetic datasets

Run `python -m ai.synthetic_data.generate` from `backend/` to generate:

- 5,000 scam calls in `scam_calls.csv`
- 500 digital-arrest scam transcripts and 200 normal calls in `digital_arrest_calls.csv`
- 100 deliberately repeated scam numbers plus synthetic caller reputations in `caller_reputations.csv`
- 3,000 fraud reports in `fraud_reports.csv`
- 2,000 counterfeit cases in `counterfeit_cases.csv`
- Labelled banknote-like image augmentations under `currency/{real,fake}/{10,20,50,100,200,500,2000}`
- 10,000 geospatial incidents in `crime_incidents.geojson`
- 3,000 graph nodes across 500 fraud networks in `fraud_network.json`

All people, numbers, accounts, incidents and locations are synthetic. No proprietary or government dataset is required.

The currency images are abstract synthetic fixtures, not scans of legal tender. Generate them with
`generate_currency_dataset()` from `ai.synthetic_data.currency_augment`; variants include rotation,
brightness, blur, contrast, JPEG compression, noise, occlusion, and shadow.
