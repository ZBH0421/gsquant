# COT Radar deployment verification

This branch exists to exercise the GitHub Pages workflow from a same-repository pull request after the first verified release. The deployment workflow still runs weekly on Saturday at 08:00 Asia/Taipei and can be started manually.

The verified deployment path enables the repository's Pages site through GitHub Actions before uploading the static artifact. Repository Pages was enabled before the final verification run. A successful CI run triggers deployment from the protected default-branch context.
