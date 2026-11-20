# Setup guide: commands we used (Windows)

The cleaned-up list of every command that worked, from the beginning until now. The failed attempts and why they
failed are in `PROGRESS.html` (Step 1, session log).

Replace `<name>` with your own name (e.g. `heat-georges`). Open **PowerShell as Administrator** for everything
(Start → type "PowerShell" → right-click → *Run as administrator*).

---

## 0. Get the repository

Laetitia created the repository. Teammates only need to clone it (after being added as a collaborator on GitHub):

```powershell
cd $HOME\Desktop
git clone https://github.com/englaetitia/Parallel_Programming-.git
```

For reference, these are the commands Laetitia used to create it:

```powershell
cd "C:\Users\User\OneDrive\Desktop\Parallel Project"
git init
git branch -M main
git add .
git commit -m "Step 0: repo structure, README, AI logging rules"
git remote add origin https://github.com/englaetitia/Parallel_Programming-.git
git push -u origin main
```

---

## 1. Install Multipass

```powershell
# Which Windows do I have? (Home or Pro)
(Get-ComputerInfo).WindowsProductName
```

**Windows Pro:**
```powershell
Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -All   # restart the PC after
winget install --id Canonical.Multipass -e --accept-source-agreements --accept-package-agreements
```

**Windows Home:**
```powershell
winget install Oracle.VirtualBox
winget install --id Canonical.Multipass -e --accept-source-agreements --accept-package-agreements
```

**Check the install:**
```powershell
winget list multipass                                          # should show Canonical.Multipass 1.17.0
Test-Path "C:\Program Files\Multipass\bin\multipass.exe"       # should show True
```

**If `multipass` is "not recognized"** (fixes the current window only; restarting Windows fixes it for good):
```powershell
$env:Path += ";C:\Program Files\Multipass\bin"
```

```powershell
multipass version            # multipass 1.17.0+win
multipass get local.driver   # hcs (Pro) or virtualbox (Home)
```

---

## 2. Get the Ubuntu 24.04 image

The normal `multipass launch` downloads about 600 MB. On a slow or unstable connection the download breaks
("Hash ... does not match"). So we download it ourselves with a command that can **resume**.

> **Shortcut:** ask Laetitia for her `noble.img` (USB / shared drive), put it in your `Downloads` folder, and skip to the fingerprint check.

```powershell
# Download. If it stops, run the SAME line again: it continues where it stopped
curl.exe -L -C - -o "$HOME\Downloads\noble.img" https://cloud-images.ubuntu.com/releases/noble/release/ubuntu-24.04-server-cloudimg-amd64.img
```

Check the file is complete (the two codes must be identical; upper/lower case doesn't matter):

```powershell
curl.exe -L https://cloud-images.ubuntu.com/releases/noble/release/SHA256SUMS | Select-String "server-cloudimg-amd64.img"
Get-FileHash "$HOME\Downloads\noble.img" -Algorithm SHA256
```

The expected code (20 Nov 2026) is:
`04e8f2461a16a44e78a370284471f29616cdd9baf1893df25807b71f985b6c94`

---

## 3. Create the VM

What worked for Laetitia (20 Nov 2026): a normal launch, on a connection where the download finished. If it fails with
"Hash ... does not match", clear the cache (as Administrator) and run the launch again:

```powershell
Stop-Service Multipass
Remove-Item -Recurse -Force "C:\ProgramData\Multipass\cache\hcs\vault\images\*"
Start-Service Multipass
multipass launch 24.04 --name heat-<name> --cpus 2 --memory 4G --disk 15G
```

You'll see `Retrieving image: xx%` (about 20 min on a slow connection), then `Waiting for initialization to complete`
(1-5 min), then `Launched`. Don't let the PC sleep.

Not tested yet: launching from your own `noble.img`: `multipass launch file:///Users/<your-windows-user>/Downloads/noble.img ...`
(note: without `C:`).

**Check it runs, and go inside the VM:**
```powershell
multipass list                 # heat-<name> should be "Running"
multipass shell heat-<name>    # the prompt becomes ubuntu@heat-<name>
```

---

## 4. Inside the VM: install the tools and get the code

Do **not** run `do-release-upgrade` even if Ubuntu suggests it: every VM must stay on 24.04.

```bash
sudo apt update
sudo apt install -y build-essential cmake git openmpi-bin libopenmpi-dev python3-numpy python3-matplotlib
mpirun --version      # Laetitia: Open MPI 4.1.6. Must be the SAME on every VM
g++ --version         # Laetitia: 13.3.0
cd ~ && git clone https://github.com/englaetitia/Parallel_Programming-.git heat
ls heat
```

If `apt install` stops partway (slow internet), run the same line again.

---

## Errors we hit and the fix

| Error | Fix |
| --- | --- |
| `multipass` is not recognized | `$env:Path += ";C:\Program Files\Multipass\bin"` or restart Windows |
| `Cannot open Multipass service` | PowerShell is not "Run as administrator" |
| `Hash of ... does not match` | The download broke: use step 2 (resumable download) |
| `Invalid file URL ... did you forget a slash?` | Use `file:///Users/...` (three slashes, no `C:`), or Option B |
