# Windows Distribution Notes

## Why Windows Can Block The Download

Current Windows release builds are made with PyInstaller. Unless a signing certificate is configured, `Blaster.exe` is unsigned. Windows Defender SmartScreen can block or warn on unsigned or low-reputation downloads, even when the file is clean.

SmartScreen uses publisher reputation and file-hash reputation. A new build has a new hash, so every new unsigned release starts with little or no reputation.

Official references:

- Microsoft SmartScreen reputation for app developers: https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation
- Microsoft Security Intelligence file submission: https://www.microsoft.com/wdsi/filesubmission

## Current Mitigations

- Release builds use PyInstaller with `--noupx`.
- The release script writes SHA256 checksums:
  - `release/package/SHA256SUMS.txt` inside the packaged archive
  - `release/SHA256SUMS.txt` next to the archive
- The release package includes this document so users can verify what they downloaded.

## Proper Public Release Path

For public distribution, use one of these:

- Publish through Microsoft Store.
- Sign every release with a trusted code-signing certificate or Microsoft Trusted Signing.
- Keep the signing identity consistent across versions.
- If Defender reports the file as malware or unwanted software, submit the clean build to Microsoft Security Intelligence for false-positive analysis.

Checksums help users verify file integrity, but checksums do not replace signing and do not by themselves prevent SmartScreen blocks.

## Optional Signing Hook

`scripts/build_release.ps1` can sign the executable when these environment variables are set:

```powershell
$env:BLASTER_SIGN_CERT_SHA1 = "<certificate sha1 thumbprint>"
$env:BLASTER_SIGNTOOL = "C:\Path\To\signtool.exe" # optional when signtool.exe is already in PATH
.\scripts\build_release.ps1
```

Without a signing certificate, the script still builds the archive, but it prints a warning that the executable is unsigned.
