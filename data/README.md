# data/

`data/raw/` is **read-only** (RULES.md #9). Nothing writes into it except `scripts/download_data.py`
(new files and `MANIFEST.json`). Derived data goes to `data/processed/`. The CSVs are not committed;
`data/raw/MANIFEST.json` (sha256, size, rows, columns, time span) is.

Sources and URLs live in `configs/data.yaml`. Fetch with `uv run python scripts/download_data.py`.

## Azure LLM Inference Trace 2023

- Files: `AzureLLMInferenceTrace_conv.csv`, `AzureLLMInferenceTrace_code.csv`
- Columns: TIMESTAMP, ContextTokens, GeneratedTokens
- Version: traces from Azure LLM inference services, collected 2023-11-11
- Licence (as stated): "The data is made available and licensed under a CC-BY Attribution License."
- Source: https://github.com/Azure/AzurePublicDataset/blob/master/AzureLLMInferenceDataset2023.md
- Citation (as given by the source):
  > Pratyush Patel, Esha Choukse, Chaojie Zhang, Aashaka Shah, Íñigo Goiri, Saeed Maleki, Ricardo Bianchini. "Splitwise: Efficient generative LLM inference using phase splitting", in Proceedings of the International Symposium on Computer Architecture (ISCA 2024). ACM, Buenos Aires, Argentina, 2024.

## BurstGPT

- Files: `BurstGPT_1.csv` (repo `data/` folder, branch `main`), `BurstGPT_3.csv` (release v2.0, adds
  `Session ID` and `Elapsed time`)
- Columns (per the repo page): Timestamp, Session ID, Elapsed time, Model, Request tokens,
  Response tokens, Total tokens, Log Type. `BurstGPT_1` may lack the first two; the manifest records
  the real columns.
- Licence (as stated): CC-BY-4.0
- Source: https://github.com/HPMLL/BurstGPT (release: https://github.com/HPMLL/BurstGPT/releases/tag/v2.0)
- Citation (as given by the source):
  ```bibtex
  @inproceedings{BurstGPT,
    author    = {Yuxin Wang and Yuhan Chen and Zeyu Li and Xueze Kang and Yuchu Fang and Yeju Zhou and Yang Zheng and Zhenheng Tang and Xin He and Rui Guo and Xin Wang and Qiang Wang and Amelie Chi Zhou and Xiaowen Chu},
    title     = {{BurstGPT}: A Real-World Workload Dataset to Optimize LLM Serving Systems},
    booktitle = {Proceedings of the 31st ACM SIGKDD Conference on Knowledge Discovery and Data Mining V.2 (KDD '25)},
    year      = {2025},
    address   = {Toronto, ON, Canada},
    publisher = {ACM},
    doi       = {https://doi.org/10.1145/3711896.3737413},
    url       = {https://doi.org/10.1145/3711896.3737413},
  }
  ```
