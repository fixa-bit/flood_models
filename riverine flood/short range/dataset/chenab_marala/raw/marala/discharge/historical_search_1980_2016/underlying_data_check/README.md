# Underlying historical daily-data follow-up

Checked 30 October 2026 following the request to download the actual daily records behind the IRSA, NEPRA and WAPDA-research references.

**No new observed daily Marala series for 1980-2016 was obtained.** The additional checks below found no downloadable historical workbook/database linked to those three documents. This is a statement about the sources and endpoints checked, not proof that the datasets do not exist elsewhere.

| Source | Check | Result |
|---|---|---|
| IRSA WCAP report | PDF embedded files and outgoing links; official Sindh Irrigation reports catalog | No embedded database/spreadsheet. Catalog links the same Volume I report, without a daily-data attachment or Volume II data export. |
| NEPRA Lucky Hydropower filing | PDF attachments and hyperlinks | No embedded files or outgoing data-download links. No underlying daily table was found in the saved filing. Directory listing returned HTTP 403; no restricted listing was accessed. |
| Dahri et al. (2016), WAPDA-sourced discharge | PDF attachments/links, IIASA repository landing page, Crossref metadata and publisher metadata endpoint | No embedded dataset. The repository lists the article PDF only. Publisher endpoint returned bibliographic metadata, without a supplementary discharge file. Main publisher HTML returned HTTP 403 in browsing. |

## Public operational-data services checked

The [IRSA public Daily Data page](http://pakirsa.gov.pk/DailyData.aspx) was successfully inspected over its published HTTP service. At inspection it linked eight recent reports dated 23-30 October 2026. It did not link the 1993-2014 historical MIS/GIS database. The site also advertises a separate login; no login or authenticated export was attempted. HTTPS connection failures are recorded separately from the successful HTTP responses.

The [Sindh Irrigation public charts](https://irrigation.sindh.gov.pk/Flows/Pakistan) use a public `api.hicsindh.pk` service. The documented page's `Flows/Tributry/Month/1` request returned 49 reported daily records including Marala from **1 September through 19 October 2026**. Exact JSON is saved as `tributary_month_sample.json`. It is a recent operational-data response, **not the requested 1980-2016 archive**, and has not been merged into the observed target. Its measurement basis and units require confirmation before training use.

Changing that date-range parameter to a 600-month historical request returned HTTP **401 Unauthorized**. No historical data were returned and no attempt was made to bypass the access response. The public rim-station bulletin index also contains recent material, rather than the requested historical period. API responses, JavaScript references and receipts are retained so the distinction is reviewable.

The official Sindh E-Library's public API was checked for reports/books and data attachments. It exposes the WCAP Volume I report, not the historical daily database. The repository [Zenodo 3825920](https://zenodo.org/records/3825920) was also examined as a possible lead: its public description specifies dimensionless drought indices (SPEI/SSI), not observed daily discharge, so it was not treated as Marala Q or downloaded as the requested target.

## Saved evidence

- `source_page_checks.json`: source-page checks, hashes and candidate links.
- `supplement_followup_checks.json`: publisher metadata, IRSA HTTP pages and access errors.
- `sindh_public_api_checks.json`: official chart/library discovery.
- `historical_api_metadata_checks.json`: public bulletin index and recent daily API response metadata.
- `long_record_endpoint_checks.json`: catalog response and the unauthorized historical request.
- Corresponding exact HTML, JSON, JavaScript and publisher XML snapshots.

The three PDF attachment/link audits are saved one directory above, ending in `_link_audit.json`. Existing discharge values remain unchanged. The existing `historical_records_request_draft.md` one directory above is still the concrete route for requesting IRSA's historical upstream daily-mean export and earlier Marala Division records. No request or message was sent to any agency or author.
