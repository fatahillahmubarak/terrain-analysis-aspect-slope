# Publishing this to GitHub (quick guide)

If you don't have a GitHub account yet:

1. Install [Git for Windows](https://git-scm.com/downloads) if you don't already have `git` available (the installer's defaults are fine).
2. Create a free GitHub account at [github.com/signup](https://github.com/signup).
3. Click the **+** icon (top right) → **New repository**. Name it e.g. `qgis-terrain-analysis-symbology`, keep it public, don't add a README/license (this project already has them), then **Create repository**.
4. Open a terminal (PowerShell/Command Prompt) *inside this project folder* and turn it into a git repository:
   ```
   git init
   git add -A
   git commit -m "Initial commit: Terrain Analysis Symbology v1.0.0"
   ```
5. GitHub will show you commands to push this local repository — they look like:
   ```
   git remote add origin https://github.com/YOUR-USERNAME/qgis-terrain-analysis-symbology.git
   git branch -M main
   git push -u origin main
   ```
6. Once pushed, open `terrain_analysis_symbology/metadata.txt` and replace the three `YOUR-GITHUB-USERNAME` placeholders in `tracker`/`repository`/`homepage` with your real repo URL, then commit and push that small change too:
   ```
   git add terrain_analysis_symbology/metadata.txt
   git commit -m "Update metadata links"
   git push
   ```

That's it — the repo is now live and linkable from your portfolio/LinkedIn.

## Making it installable straight from GitHub (optional, later)

Once you have some usage/feedback and want wider distribution, you can:

- Submit it to the official [QGIS Plugin Repository](https://plugins.qgis.org/) (requires a free account there, plus zipping `terrain_analysis_symbology/` per their submission guide) — this is what lets any QGIS user find and install it straight from **Plugins → Manage and Install Plugins** without knowing GitHub exists.
- Or just share the GitHub link / a release ZIP directly — anyone can install it manually (see the "Install as a QGIS plugin" and "Install from ZIP" sections in `README.md`).
