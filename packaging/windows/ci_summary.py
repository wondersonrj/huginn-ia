"""Publish test evidence in the public Actions job summary, including failures."""
import os
from pathlib import Path
import xml.etree.ElementTree as ET

report = Path('release/backend-tests.xml')
summary = Path(os.environ['GITHUB_STEP_SUMMARY'])
with summary.open('a', encoding='utf-8') as out:
    out.write('## Windows backend test evidence\n\n')
    if not report.is_file():
        out.write('No JUnit report was generated; backend tests did not complete.\n')
    else:
        root = ET.parse(report).getroot()
        for suite in root.iter('testsuite'):
            out.write(f"Tests: {suite.get('tests')}; failures: {suite.get('failures')}; errors: {suite.get('errors')}; skipped: {suite.get('skipped')}\n\n")
        for case in root.iter('testcase'):
            for kind in ['failure','error']:
                error = case.find(kind)
                if error is not None:
                    message = (error.text or error.get('message', ''))[-10000:]
                    escaped = message.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
                    print(f"::error title={case.get('name')}::{escaped}")
                    out.write(f"### {case.get('classname')}.{case.get('name')}\n\n```text\n{(error.text or '')[-12000:]}\n```\n\n")
