# Robust Literature Review Pipeline

[![Render & Release](https://github.com/htlin222/robust-lit-review/actions/workflows/render-release.yml/badge.svg)](https://github.com/htlin222/robust-lit-review/actions/workflows/render-release.yml)

自動化系統性文獻回顧工具，搜尋 **Scopus**、**PubMed** 和 **Embase** 三大資料庫，依期刊影響力 (CiteScore/SJR) 篩選，驗證每一筆 DOI，並產生可直接投稿的文獻回顧文章。

## 功能特色

給定一個研究主題，本工具會自動完成以下流程：

1. **平行搜尋** 三大資料庫 (Scopus、PubMed、Embase)
2. **去除重複** 依 DOI 和標題跨資料庫去重
3. **品質篩選** 僅保留高影響力期刊 (CiteScore >= 3.0、Q1/Q2)
4. **DOI 驗證** 透過 doi.org API 驗證每一筆文獻
5. **擷取完整摘要** 透過 PubMed/Scopus Abstract Retrieval API
6. **結構化資料萃取** 從摘要中提取樣本數、p 值、劑量、閾值等
7. **均衡主題涵蓋** 確保涵蓋流行病學、病理機轉、診斷、治療、預後等面向
8. **開放取用連結** 透過 Unpaywall 取得 OA 連結
9. **匯出至 Zotero** 自動建立文獻集合
10. **模組化平行寫作** 使用 Quarto `{{< include >}}` 架構，8 個章節同時撰寫
11. **渲染輸出** PDF (含 PRISMA TikZ 流程圖) 和 DOCX，使用 AMA 引用格式
12. **自動發布** 透過 GitHub Actions 自動產生 Release

## 快速開始

```bash
# 安裝
uv venv && source .venv/bin/activate && uv pip install -e "."

# 設定 API 金鑰
cp .env.example .env
# 編輯 .env 填入你的 API 金鑰

# 執行文獻回顧
lit-review review "你的研究主題" --target 50 --min-citescore 3.0

# 驗證現有 BibTeX 中的 DOI
lit-review validate output/references.bib

# 檢查 API 設定
lit-review check-config
```

## 所需 API 金鑰

| 服務 | 用途 | 取得方式 |
|------|------|---------|
| Scopus | 文獻搜尋 + CiteScore/SJR 指標 | [Elsevier Developer Portal](https://dev.elsevier.com/) |
| PubMed | 生物醫學文獻搜尋 | [NCBI API Key](https://ncbiinsights.ncbi.nlm.nih.gov/2017/11/02/new-api-keys-for-the-e-utilities/) |
| Embase | 醫學文獻 (透過 Elsevier) | 同 Scopus |
| Unpaywall | DOI 驗證 + 開放取用連結 | [Unpaywall](https://unpaywall.org/) (僅需 email) |
| Zotero | 參考文獻管理匯出 | [Zotero Settings](https://www.zotero.org/settings/keys) |

## 流程架構

```
研究主題輸入
    |
    v
[Scopus API] --+-- [PubMed API] --+-- [Embase API]    (平行搜尋)
    |                |                  |
    +--------+-------+------------------+
             |
         去除重複 (依 DOI/標題)
             |
         品質篩選 (CiteScore >= 3.0)
             |
         DOI 驗證 (doi.org API)
             |
         擷取完整摘要 (PubMed/Scopus)
             |
         均衡主題選擇
             |
         結構化資料萃取
             |
         開放取用資訊 (Unpaywall)
             |
         Zotero 匯出
             |
    +--------+--------+--------+
    |        |        |        |
  .bib    sections/  統計    PRISMA
             |                (TikZ)
    8 個平行寫作代理
             |
         main.qmd ({{< include >}})
             |
    +--------+--------+
    |                 |
   PDF              DOCX
```

## 模組化章節架構

使用 Quarto `{{< include >}}` 語法平行撰寫：

```
output/
  literature_review.qmd          # 主文件 (含 include 指令)
  references.bib                 # BibTeX 參考文獻
  prisma-flow-diagram/           # PRISMA TikZ 套件
  sections/
    00-abstract.qmd              # 結構化摘要
    01-introduction.qmd          # 臨床意義、歷史、研究目標
    02-methods.qmd               # PRISMA 流程、搜尋策略、品質評估
    03-pathogenesis.qmd          # IFN-gamma 軸、細胞激素、鐵蛋白、基因
    04-diagnosis.qmd             # HLH-2004、HLH-2024、HScore、MAS 標準
    05-etiology.qmd              # 感染、惡性腫瘤、MAS、醫源性 (CAR-T、ICI)
    06-treatment.qmd             # HLH-94 劑量、標靶治療、HSCT
    07-covid.qmd                 # COVID-19 與 HLH 範式
    08-discussion.qmd            # 綜合討論、爭議、未來方向
```

## 輸出檔案

| 檔案 | 說明 |
|------|------|
| `output/literature_review.pdf` | PDF 格式，含 AMA 引用 + PRISMA TikZ 流程圖 |
| `output/literature_review.docx` | Word 文件 |
| `output/literature_review.qmd` | Quarto 原始檔 (可編輯) |
| `output/references.bib` | BibTeX 參考文獻 |

## GitHub Actions

推送至 `main` 分支時，工作流程自動：
- 渲染 Quarto 為 PDF + DOCX
- 建立 GitHub Release 並附加所有成品
- 成品保留 90 天

## 品質標準

- 僅收錄 Q1/Q2 期刊 (CiteScore >= 3.0)
- 100% DOI 驗證 (doi.org handle API)
- 符合 PRISMA 2020 規範 (TikZ 流程圖)
- AMA 引用格式
- 均衡的主題涵蓋 (非僅取最高引用數)
- 從摘要中萃取結構化數據
- 跨資料庫去重

## Claude Code 整合

本專案包含 Claude Code 技能：

- `/lit-review` -- 執行完整流程，含模組化平行寫作
- `/brainstorm-topic` -- 腦力激盪並優化搜尋策略

## 引用本專案

如果您在研究中使用了本工具，請引用：

### BibTeX

```bibtex
@software{lin2026robustlitreview,
  author       = {Lin, Hsieh-Ting},
  title        = {Robust Literature Review Pipeline: Automated Systematic Review with Multi-Database Search, DOI Validation, and Publication-Ready Output},
  year         = {2026},
  publisher    = {GitHub},
  url          = {https://github.com/htlin222/robust-lit-review},
  version      = {1.0.0}
}
```

### APA

Lin, H.-T. (2026). *Robust Literature Review Pipeline: Automated systematic review with multi-database search, DOI validation, and publication-ready output* (Version 1.0.0) [Computer software]. GitHub. https://github.com/htlin222/robust-lit-review

### AMA

Lin HT. Robust Literature Review Pipeline: Automated Systematic Review with Multi-Database Search, DOI Validation, and Publication-Ready Output. Version 1.0.0. GitHub; 2026. Accessed March 25, 2026. https://github.com/htlin222/robust-lit-review

## 授權條款

MIT
