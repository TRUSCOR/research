# Paper-build tooling

This directory builds and validates the private P1 and P4-P6 review packages
and the author-approved PF flagship public preprint package.
It never uploads or publishes them.

## Verified build tools

The 2026-08-03 build used temporary official release binaries verified before
execution:

| Tool | Version | Licence | Verified official release-asset SHA-256 |
|---|---:|---|---|
| Pandoc | 3.10.1 | GPL-2.0-or-later tool; output is not thereby relicensed | `4725a1883e2171c2e181e6fd45003acb59ca4e9cbe031fdd3b79ef0d697d36aa` |
| Tectonic | 0.16.9 | MIT | `131a24604785a9600989a3d91225f597df52ac06f00aeffe86fd529f99ee5cdd` |
| Poppler Windows package | 26.02.0-0 | MIT packaging; bundled component licences apply | `993e4a94376ed712fafc7058d724ea0b943d118bbd2305cd9ed55174eb85cda5` |

Acquire future copies only from the official Pandoc and Tectonic release
pages, verify version, licence, and release checksum, and pass their absolute
paths explicitly:

```powershell
python private\research\papers\tools\build_publication_packages.py `
  --pandoc C:\absolute\path\to\pandoc.exe `
  --tectonic C:\absolute\path\to\tectonic.exe
```

Tectonic may download its official TeX support bundle on first use. The build
requires no model, API key, GPU, client data, or SOVA credential.

Validation uses Python 3.11 with pinned `pypdf==6.14.2`. Figure generation used
`matplotlib==3.10.8`. Both are build/test dependencies only and are not SOVA
runtime dependencies:

```powershell
<bundled-python> -X utf8 private\research\papers\tools\validate_publication_packages.py
```

The validator checks retained experiment values, citation keys, figures,
source-archive paths, PDF text/structure, digests, private Git boundaries, and
prohibited overclaims. Visual page rendering remains a separate requirement.
