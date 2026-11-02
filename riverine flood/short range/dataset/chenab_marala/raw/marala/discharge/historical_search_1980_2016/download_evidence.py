"""Save public historical-data evidence; never modify or synthesize discharge."""
import hashlib
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent
SOURCES = {
    'irsa_wcap_volume1.pdf': 'https://irrigation.sindh.gov.pk/files/books/Final-Report-Volume-I-WCAP.pdf',
    'nepra_lucky_hydropower_2011.pdf': 'https://nepra.org.pk/tariff/Tariff/Petitions/2011/Tariff%20Petition%20of%20Olympus%20Energy%2020MW%20Lucky%20Hydropower%20Project.pdf',
    'ihe_chenab_discharge_source_page14.pdf': 'https://ihedelftrepository.contentdm.oclc.org/digital/api/collection/masters2/id/84848/download',
    'dahri_2016_precipitation_discharge.pdf': 'https://pure.iiasa.ac.at/id/eprint/11829/1/An%20appraisal%20of%20precipitation%20distribution%20in%20the%20high-altitude%20catchments%20of%20the%20Indus%20basin.pdf',
    'wur_droppers_thesis.pdf': 'https://edepot.wur.nl/569432',
    'worldbank_marala_1977_1991.pdf': 'https://documents1.worldbank.org/curated/en/454701468775827683/pdf/multi-page.pdf',
}


def collect(item):
    name, url = item
    path = ROOT / name
    receipt = dict(url=url, filename=name, checked_utc=datetime.now(timezone.utc).isoformat())
    try:
        if path.exists():
            data = path.read_bytes()
            receipt['retrieval'] = 'reused exact download'
        else:
            request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Marala historical observed discharge research)'})
            with urllib.request.urlopen(request, timeout=45) as response:
                data = response.read()
                receipt['final_url'] = response.url
                receipt['content_type'] = response.headers.get('Content-Type')
            if not data.startswith(b'%PDF-'):
                raise ValueError('Response is not a PDF')
            path.write_bytes(data)
            receipt['retrieval'] = 'downloaded public PDF'
        receipt.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        with pymupdf.open(stream=data, filetype='pdf') as doc:
            receipt['pdf_pages'] = len(doc)
            receipt['embedded_files'] = doc.embfile_names()
            receipt['pages_mentioning_marala_1_based'] = [i + 1 for i, page in enumerate(doc) if 'marala' in page.get_text().casefold()]
            receipt['first_page_title_preview'] = doc[0].get_text()[:220].strip()
        receipt['status'] = 'saved'
    except Exception as exc:
        receipt.update(status='failed', error=str(exc))
    return receipt


def main():
    receipts = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(collect, item) for item in SOURCES.items()]
        for future in as_completed(futures):
            row = future.result()
            receipts.append(row)
            print(row['filename'], row['status'], row.get('pdf_pages', ''), row.get('error', ''), flush=True)
    (ROOT / 'download_receipts.json').write_text(json.dumps(receipts, indent=2) + '\n')
    for row in receipts:
        preview = row.get('first_page_title_preview', '').encode('ascii', 'backslashreplace').decode()
        print(row['filename'], row.get('pages_mentioning_marala_1_based', []), preview, flush=True)


if __name__ == '__main__':
    main()
