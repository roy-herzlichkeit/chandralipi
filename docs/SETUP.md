# Setting up Chandralipi on Windows, Ubuntu or macOS

This guide takes a fresh machine to a working install: tests pass, the dashboard opens, and a registration can be run. Each section says what works on that system and what does not.

| | Ubuntu / Linux | Windows | macOS |
|---|---|---|---|
| Recommended route | native | **WSL2 + Ubuntu** (best), or native with Git Bash | native |
| GPU (CUDA) matching | yes, NVIDIA | yes, NVIDIA (native or WSL2) | **no** — runs on CPU (the code has no Apple-GPU/MPS path) |
| Setup script `scripts/setup.sh` | yes | yes, in WSL2 or Git Bash | yes |
| Everything else (`scripts/*.sh`) | yes | WSL2: yes; Git Bash: mostly | yes |

What you need everywhere:
- **Python 3.10 or newer** (the project is developed on 3.12).
- **Git**.
- About **5 GB** of disk for the environment (PyTorch is most of it). Real data is extra: 57 GB on the development machine, budget 120 GB (`docs/plan/CLARIFY.md` Q17).
- Optional: **Node.js 18 or newer** for the web showcase in `web/`.
- Optional: an **NVIDIA GPU** with a recent driver for CUDA. 8 GB of VRAM is the tested size.
- Optional: `zstd` to pack and unpack data bundles faster (gzip is used otherwise).

---

## 1. Ubuntu (22.04 / 24.04) and other Linux

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip zstd rsync
# optional, for the web showcase:
sudo apt install -y nodejs npm        # check: node --version  (needs 18+; use NodeSource or nvm if older)

git clone https://github.com/roy-herzlichkeit/chandralipi.git
cd chandralipi
./scripts/setup.sh                     # CPU install: .venv + dependencies + checks
# or, with an NVIDIA GPU:
./scripts/setup.sh --cuda              # CUDA 13 PyTorch build
./scripts/setup.sh --cuda --cuda-index cu126   # if the driver is too old for CUDA 13
```

Check the GPU first if you want CUDA: `nvidia-smi` must list the card. The setup script ends by printing `torch.version.cuda` and whether CUDA is available. With `--cuda`, it refuses to finish if a CPU-only PyTorch was installed.

---

## 2. Windows 10 / 11

### Option A — WSL2 (recommended)

WSL2 runs a real Ubuntu inside Windows, so every script works unchanged and CUDA works with the normal Windows NVIDIA driver.

1. In PowerShell **as administrator**: `wsl --install -d Ubuntu-24.04`, then restart and create the Linux user it asks for.
2. For CUDA: install the normal **Windows** NVIDIA driver. Do **not** install a Linux driver inside WSL. In the Ubuntu window, `nvidia-smi` should list the card.
3. In the Ubuntu window, follow **section 1** exactly.
4. Clone inside the Linux file system (for example `~/chandralipi`), not under `/mnt/c/...`: reading large rasters across the Windows boundary is many times slower.
5. The dashboard prints a `localhost` URL. Open it in your Windows browser; WSL2 forwards it.

### Option B — native Windows with Git Bash

1. Install **Python 3.12** from python.org (tick "Add python.exe to PATH"), **Git for Windows** (this includes Git Bash), and optionally **Node.js LTS**.
2. Open **Git Bash** (not PowerShell or cmd) and run:
   ```bash
   git clone https://github.com/roy-herzlichkeit/chandralipi.git
   cd chandralipi
   PYTHON=python ./scripts/setup.sh             # or: ./scripts/setup.sh --python python
   PYTHON=python ./scripts/setup.sh --cuda      # with an NVIDIA GPU
   ```
   The scripts detect `.venv/Scripts/python.exe` automatically.
3. Known limits on native Windows:
   - The setup script's last line (`.venv/bin/lunar-reg env`) fails harmlessly. Run `.venv/Scripts/lunar-reg env` yourself.
   - Commands in this repo's docs write `.venv/bin/python`. On native Windows use `.venv/Scripts/python` instead.
   - `rsync` and `zstd` are not in Git Bash by default. The setup script falls back to `cp`, and data bundles fall back to gzip.
   - Some phase scripts (`Phase_*/harness/*.sh`) use `timeout` and `sha256sum`, which Git Bash has, and `systemd-run`, which it does not. Use WSL2 for the full harness.

---

## 3. macOS (Apple silicon or Intel)

```bash
xcode-select --install                 # command-line tools (git, compilers)
# Homebrew from https://brew.sh, then:
brew install python@3.12 git zstd node
git clone https://github.com/roy-herzlichkeit/chandralipi.git
cd chandralipi
./scripts/setup.sh --python python3.12
```

- There is no CUDA on a Mac, so do not pass `--cuda`. PyTorch installs its normal macOS build, and all matching runs on the CPU.
- The neural matchers (LightGlue, LoFTR) work on CPU but are much slower than on a GPU. Keep the working scale coarse (for example `--gsd 4` or coarser in `scripts/run_vikram.py`) on a laptop.
- If `rasterio` has no wheel for your Python version, install GDAL first (`brew install gdal`) and re-run the setup script.

---

## 4. Check the install (all systems)

From the repository root, with `PY` = `.venv/bin/python` (or `.venv/Scripts/python` on native Windows):

```bash
$PY -m lunar_reg.cli env           # Python, PyTorch, CUDA and device memory budget
bash scripts/ci.sh                 # lint + the CPU test suite (a few minutes)
./scripts/run_dashboard.sh         # results browser; prints a URL to open
```

`scripts/ci.sh` runs every test that needs no GPU, no downloaded data and no model weights. Tests marked `gpu`, `data` or `weights` are skipped with a reason when the resource is missing.

### Optional extras
`setup.sh` installs the `dev` and `dashboard` extras. Add others with `--extras`:

| extra | what it adds | install |
|---|---|---|
| `spice` | Sun geometry from NASA SPICE kernels (`ingest/sun.py`) | `./scripts/setup.sh --extras dev,dashboard,spice` |
| `notebooks` | JupyterLab | `./scripts/setup.sh --extras dev,dashboard,notebooks` |

Neural matcher weights (LoFTR, LightGlue) are downloaded automatically on first use into `~/.cache/torch/hub/checkpoints`. That needs internet once.

---

## 5. Getting data

`data/` is not in git. There are three ways to fill it:

1. **Copy from a machine that has it** (fastest).
   - On that machine: `./scripts/pack_data.sh`. It writes a `.tar.zst` or `.tar.gz` bundle.
   - On the new machine: `./scripts/setup.sh --data /path/to/bundle`.

   The setup script unpacks the bundle, rebuilds the results index and reports how many results rows it found.
2. **Public reference data** (NASA LRO, JAXA SELENE, NAIF SPICE): `$PY scripts/fetch_public.py --dry-run` shows the plan, then run it without `--dry-run`. Every file is recorded with its SHA-256 in `data/raw/DOWNLOADS.json`.
3. **Chandrayaan-2 data (ISRO PRADAN)** is downloaded **by a person only**. Log in, pick products and download them; never script the portal. Exact product names, folder layout and the disk budget are in `Phase_1/LLD/downloads.md`. Background on the archive is in `docs/DATA_ACQUISITION.md`.

After any download, check it: `$PY scripts/verify_downloads.py`.

---

## 6. Web showcase (optional)

```bash
$PY scripts/export_web_data.py     # refresh web/public/data from the results store
cd web
npm install
npm run dev                         # opens on http://localhost:5173
```

`./scripts/up.sh` starts the dashboard and the web showcase together (`--host` makes them visible to other devices on the LAN).

---

## 7. Common problems

| symptom | fix |
|---|---|
| `venv creation failed` on Ubuntu | `sudo apt install python3-venv` |
| `--cuda was given but torch.version.cuda is None` | a CPU PyTorch was installed: re-run with `--cuda --force` |
| CUDA build installs but `cuda=False` | driver too old for CUDA 13: use `--cuda --cuda-index cu126`; on WSL2, update the **Windows** driver |
| dashboard opens empty | no results yet: copy a data bundle (section 5) or run `scripts/run_vikram.py` |
| `ImportError` mentioning the `spice` extra | install it: `--extras dev,dashboard,spice` |
| very slow raster reads on WSL2 | the repo is under `/mnt/c/`; clone it inside the Linux home directory |
| out-of-memory on the GPU | expected on small cards; the run records it as an `oom` outcome. Use a coarser `--gsd` or fewer neural matchers |
